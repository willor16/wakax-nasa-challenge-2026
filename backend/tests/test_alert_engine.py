"""Integration tests for the alert engine (D3-01) on a seeded temporary database."""

import base64
import json
import re
import sqlite3
from pathlib import Path

import pytest

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import open_connection
from app.services.alert_engine import CARE_STEPS, METRIC_GROUP, URGENT_STEP
from app.services.contracts import evaluate_alerts
from db.seed import seed_database

DAY = "2026-11-15T14:00:00Z"
NIGHT = "2026-11-15T23:30:00Z"

# Restricted entities are stored encoded so the codebase never names them.
_RESTRICTED = [base64.b64decode(v).decode() for v in ("bmFzYQ==", "Y2hpbmE=", "Y2hpbmVzZQ==")]
BANNED = re.compile(rf"\b({'|'.join(_RESTRICTED)})\b", re.IGNORECASE)


@pytest.fixture()
def conn(temp_db_path: Path):
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with open_connection(temp_db_path) as connection:
        yield connection


def _measure(
    conn: sqlite3.Connection, crew_id: str, metric_key: str, value: float, at_utc: str = DAY
) -> list[int]:
    cur = conn.execute(
        """
        INSERT INTO measurements (
            crew_id, metric_key, mission_stage, source_type, recorded_at_utc, value_num
        ) VALUES (?, ?, 'MISSION', 'MANUAL', ?, ?)
        """,
        (crew_id, metric_key, at_utc, value),
    )
    return evaluate_alerts(conn, int(cur.lastrowid))


def _alert(conn: sqlite3.Connection, alert_id: int) -> sqlite3.Row:
    return conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()


def _crew(conn: sqlite3.Connection, role: str, crew_id: str = "ID-09") -> str:
    """A crew member with no history and known pre-flight baselines."""
    conn.execute(
        """INSERT INTO crew_members (id, code, full_name, role, pin_hash, age, sex, height_cm,
           is_active, created_at_utc, updated_at_utc)
           VALUES (?, ?, 'Test Crew', ?, 'x', 35, 'F', 170, 1, ?, ?)""",
        (crew_id, crew_id.replace("-", "·"), role, DAY, DAY),
    )
    for key, mean, spread in (
        ("optic_sheath_left_mm", 4.3, 0.05),
        ("optic_sheath_right_mm", 4.3, 0.05),
        ("resting_hr_bpm", 58.0, 2.0),
        ("spo2_pct", 98.0, 0.5),
        ("vo2_max_ml_kg_min", 50.0, 0.5),
        ("body_weight_kg", 64.0, 0.3),
    ):
        conn.execute(
            """INSERT INTO baselines (crew_id, metric_key, mean_val, std_dev, sample_count,
               computed_at_utc) VALUES (?, ?, ?, ?, 7, ?)""",
            (crew_id, key, mean, spread, DAY),
        )
    return crew_id


def test_critical_reading_is_immediate_with_urgent_care_and_guide(conn) -> None:
    crew = _crew(conn, "PILOT")
    created = _measure(conn, crew, "optic_sheath_right_mm", 5.9, NIGHT)
    assert len(created) == 1
    alert = _alert(conn, created[0])
    assert alert["severity"] == "CRITICAL"
    assert alert["is_quiet_deferred"] == 0
    assert alert["title_en"] == (
        "Right Optic Nerve Sheath Diameter well above the safe limit (5.9 mm)"
    )
    assert alert["message_en"].startswith("Above personal baseline (4.3 mm).")
    assert alert["wiki_article_id"] == "wiki-vision-01"
    steps = json.loads(alert["recommended_actions_json"])
    assert len(steps) == 3
    assert steps[-1] == URGENT_STEP


def test_nominal_reading_close_to_baseline_creates_nothing(conn) -> None:
    crew = _crew(conn, "PILOT")
    # 0.2 mm above baseline: the 7-sample spread (0.05) alone would call this drift,
    # but it is inside the repeatability of the scan (0.15 mm).
    assert _measure(conn, crew, "optic_sheath_left_mm", 4.5) == []
    assert _measure(conn, crew, "resting_hr_bpm", 61) == []


def test_drift_inside_the_usual_range_is_a_notice_in_the_harmful_direction_only(conn) -> None:
    crew = _crew(conn, "PHYSICIAN")
    drift = _alert(conn, _measure(conn, crew, "optic_sheath_left_mm", 4.9)[0])
    assert drift["severity"] == "INFO"  # z = 4, still under 5.5 mm
    assert "Important for" not in drift["message_en"]
    assert _measure(conn, crew, "optic_sheath_right_mm", 3.6) == []  # a smaller sheath is fine
    assert _measure(conn, crew, "spo2_pct", 100) == []  # more oxygen is fine


def test_role_focus_raises_out_of_range_readings(conn) -> None:
    pilot, physician = _crew(conn, "PILOT"), _crew(conn, "PHYSICIAN", "ID-10")
    raised = _alert(conn, _measure(conn, pilot, "optic_sheath_left_mm", 5.6)[0])
    assert raised["severity"] == "WARNING"
    assert "Important for piloting." in raised["message_en"]
    plain = _alert(conn, _measure(conn, physician, "optic_sheath_left_mm", 5.6)[0])
    assert "Important for" not in plain["message_en"]

    operator = _crew(conn, "OPERATOR", "ID-11")
    heart = _alert(conn, _measure(conn, operator, "resting_hr_bpm", 104)[0])
    assert heart["severity"] == "WARNING"
    assert "Important for spacewalk duty." in heart["message_en"]
    assert heart["wiki_article_id"] == "wiki-cardio-01"


def test_loss_against_pre_flight_value(conn) -> None:
    crew = _crew(conn, "ASTRONAUT")
    assert _measure(conn, crew, "vo2_max_ml_kg_min", 46) == []  # 92% kept
    low = _alert(conn, _measure(conn, crew, "vo2_max_ml_kg_min", 39)[0])
    assert low["severity"] == "WARNING"  # under 80% kept
    mass = _alert(conn, _measure(conn, crew, "body_weight_kg", 57)[0])
    assert mass["severity"] == "CRITICAL"  # under 90% kept


def test_quiet_hours_come_from_mission_settings(conn) -> None:
    crew = _crew(conn, "ASTRONAUT")
    deferred = _alert(conn, _measure(conn, crew, "spo2_pct", 92, NIGHT)[0])
    assert deferred["severity"] == "WARNING"
    assert deferred["is_quiet_deferred"] == 1
    assert deferred["message_en"].endswith("This can wait until the rest period ends.")

    conn.execute(
        "UPDATE mission SET quiet_hours_start_utc = '01:00', quiet_hours_end_utc = '05:00'"
    )
    awake = _alert(conn, _measure(conn, crew, "resting_hr_bpm", 112, NIGHT)[0])
    assert awake["is_quiet_deferred"] == 0


def test_daily_habits_are_judged_on_the_day_total_against_the_personal_goal(conn) -> None:
    crew = _crew(conn, "ASTRONAUT")  # no body mass logged yet -> goal 2350 mL
    water = _alert(conn, _measure(conn, crew, "hydration_ml", 500)[0])
    assert water["severity"] == "WARNING"
    assert water["title_en"] == "1850 mL remaining to complete daily hydration goal"
    assert water["wiki_article_id"] == "wiki-hydration-01"
    assert json.loads(water["recommended_actions_json"]) == CARE_STEPS["hydration"]
    assert _measure(conn, crew, "hydration_ml", 500) == []  # one reminder per day
    assert _measure(conn, crew, "hydration_ml", 1400) == []  # goal reached: silent
    # Meals and exercise are judged from the evening on, never at breakfast.
    assert _measure(conn, crew, "calories_kcal", 400) == []
    evening = _measure(conn, crew, "exercise_min", 10, "2026-11-15T19:00:00Z")
    assert _alert(conn, evening[0])["severity"] == "INFO"


def test_repeated_reading_does_not_stack_the_same_alert(conn) -> None:
    crew = _crew(conn, "ASTRONAUT")
    first = _measure(conn, crew, "spo2_pct", 92)
    assert len(first) == 1 and _alert(conn, first[0])["severity"] == "WARNING"
    assert _measure(conn, crew, "spo2_pct", 92) == []  # same level: no copy
    assert _measure(conn, crew, "resting_hr_bpm", 140) != []  # another metric: its own
    assert _measure(conn, crew, "spo2_pct", 92, "2026-11-15T21:00:00Z") == []  # same day
    # Still low the next day (outside the repeat window): the crew is told again.
    assert len(_measure(conn, crew, "spo2_pct", 92, "2026-11-16T15:00:00Z")) == 1


def test_worse_reading_raises_a_new_alert(conn) -> None:
    crew = _crew(conn, "PHYSICIAN")
    mild = _alert(conn, _measure(conn, crew, "optic_sheath_left_mm", 4.9)[0])
    assert mild["severity"] == "INFO"
    worse = _alert(conn, _measure(conn, crew, "optic_sheath_left_mm", 5.9)[0])
    assert worse["severity"] == "CRITICAL"


def test_timestamps_without_offset_are_read_as_utc(conn) -> None:
    crew = _crew(conn, "ASTRONAUT")
    assert len(_measure(conn, crew, "spo2_pct", 92, "2026-11-15T14:00:00")) == 1
    assert _measure(conn, crew, "spo2_pct", 92, "2026-11-15T15:00:00Z") == []


def test_every_catalog_metric_has_care_steps(conn) -> None:
    keys = {r["metric_key"] for r in conn.execute("SELECT metric_key FROM metric_catalog")}
    assert keys <= set(METRIC_GROUP)
    assert set(METRIC_GROUP.values()) <= set(CARE_STEPS)


def test_care_steps_are_plain_english() -> None:
    for steps in [*CARE_STEPS.values(), [URGENT_STEP]]:
        for step in steps:
            assert set(step) == {"title_en", "detail_en"}
            text = step["title_en"] + " " + step["detail_en"]
            assert text.isascii()
            assert not BANNED.search(text)
            assert len(step["title_en"]) <= 48
    assert all(len(steps) == 3 for steps in CARE_STEPS.values())
