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


def _measure(conn: sqlite3.Connection, crew_id: str, metric_key: str, value: float,
             at_utc: str = DAY) -> list[int]:
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


def test_critical_reading_is_immediate_with_urgent_care_and_guide(conn) -> None:
    created = _measure(conn, "ID-01", "optic_sheath_right_mm", 5.9, NIGHT)
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
    assert _measure(conn, "ID-01", "optic_sheath_left_mm", 4.3) == []


def test_pilot_vision_drift_is_raised_but_physician_is_not(conn) -> None:
    # Both baselines: mean ~4.0-4.2 mm, spread 0.2 mm -> z = 2.75 (INFO by drift alone).
    pilot = _alert(conn, _measure(conn, "ID-01", "optic_sheath_left_mm", 4.75)[0])
    assert pilot["severity"] == "WARNING"
    assert "Important for piloting." in pilot["message_en"]

    physician = _alert(conn, _measure(conn, "ID-03", "optic_sheath_left_mm", 4.55)[0])
    assert physician["severity"] == "INFO"
    assert "Important for" not in physician["message_en"]


def test_operator_heart_drift_is_raised(conn) -> None:
    # ID-02 resting heart rate baseline 58 bpm, spread 2.32 -> 64 bpm is z = 2.6.
    alert = _alert(conn, _measure(conn, "ID-02", "resting_hr_bpm", 64)[0])
    assert alert["severity"] == "WARNING"
    assert "Important for spacewalk duty." in alert["message_en"]
    assert alert["wiki_article_id"] == "wiki-cardio-01"


def test_quiet_hours_come_from_mission_settings(conn) -> None:
    # 2000 mL is below the usual range and far below this crew member's own average.
    deferred = _alert(conn, _measure(conn, "ID-04", "hydration_ml", 2000, NIGHT)[0])
    assert deferred["severity"] == "WARNING"
    assert deferred["is_quiet_deferred"] == 1
    assert deferred["message_en"].endswith("This can wait until the rest period ends.")

    conn.execute(
        "UPDATE mission SET quiet_hours_start_utc = '01:00', quiet_hours_end_utc = '05:00'"
    )
    conn.execute("UPDATE alerts SET acknowledged_at_utc = ? WHERE id = ?", (NIGHT, deferred["id"]))
    awake = _alert(conn, _measure(conn, "ID-04", "hydration_ml", 2000, NIGHT)[0])
    assert awake["is_quiet_deferred"] == 0


def test_cabin_air_links_its_protocol_and_unlinked_groups_stay_empty(conn) -> None:
    co2 = _alert(conn, _measure(conn, "ID-01", "cabin_co2_ppm", 3200)[0])
    assert co2["severity"] == "WARNING"
    assert co2["wiki_article_id"] == "wiki-co2-01"

    water = _alert(conn, _measure(conn, "ID-01", "hydration_ml", 1500)[0])
    assert water["wiki_article_id"] is None
    assert json.loads(water["recommended_actions_json"]) == CARE_STEPS["hydration"]


def test_repeated_reading_does_not_stack_the_same_alert(conn) -> None:
    conn.execute("UPDATE alerts SET acknowledged_at_utc = ? WHERE crew_id = 'ID-04'", (DAY,))
    first = _measure(conn, "ID-04", "hydration_ml", 2000)
    assert len(first) == 1 and _alert(conn, first[0])["severity"] == "WARNING"
    assert _measure(conn, "ID-04", "hydration_ml", 2050) == []      # same level: no copy
    assert _measure(conn, "ID-04", "resting_hr_bpm", 140) != []     # another metric: its own
    # Still low late that day (outside the repeat window): the crew is told again.
    assert len(_measure(conn, "ID-04", "hydration_ml", 2000, "2026-11-15T21:00:00Z")) == 1
    conn.execute("UPDATE alerts SET acknowledged_at_utc = ? WHERE crew_id = 'ID-04'", (DAY,))
    first = _measure(conn, "ID-04", "hydration_ml", 2000)

    # Once confirmed, a reading that is still out of range raises a new alert.
    conn.execute("UPDATE alerts SET acknowledged_at_utc = ? WHERE id = ?", (DAY, first[0]))
    assert len(_measure(conn, "ID-04", "hydration_ml", 2000)) == 1


def test_worse_reading_raises_a_new_alert(conn) -> None:
    conn.execute("UPDATE alerts SET acknowledged_at_utc = ? WHERE crew_id = 'ID-03'", (DAY,))
    mild = _alert(conn, _measure(conn, "ID-03", "optic_sheath_left_mm", 4.55)[0])
    assert mild["severity"] == "INFO"
    worse = _alert(conn, _measure(conn, "ID-03", "optic_sheath_left_mm", 5.9)[0])
    assert worse["severity"] == "CRITICAL"


def test_every_catalog_metric_has_care_steps(conn) -> None:
    keys = {r["metric_key"] for r in conn.execute("SELECT metric_key FROM metric_catalog")}
    assert keys <= set(METRIC_GROUP)


def test_care_steps_are_plain_english() -> None:
    for steps in [*CARE_STEPS.values(), [URGENT_STEP]]:
        for step in steps:
            assert set(step) == {"title_en", "detail_en"}
            text = step["title_en"] + " " + step["detail_en"]
            assert text.isascii()
            assert not BANNED.search(text)
            assert len(step["title_en"]) <= 48
    assert all(len(steps) == 3 for steps in CARE_STEPS.values())
