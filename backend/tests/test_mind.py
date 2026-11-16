"""Tests for psychological check-ins, the reaction test and the profile (D3-03)."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import open_connection
from app.main import app as fastapi_app
from app.services.mind import (
    calmness,
    ensure_mind_columns,
    psych_profile,
    save_checkin,
    save_reaction_session,
    score_behavioral_matrix,
    score_reaction_test,
    stability_pct,
    stress_index,
    wellbeing_index,
)
from db.seed import seed_database

PINS = {"ID-01": "1042", "ID-02": "2084"}


# ------------------------------------------------------------ pure scoring ---

def test_wellbeing_index_reverses_stress_and_isolation() -> None:
    assert wellbeing_index(5, 1, 1, 5) == 100.0
    assert wellbeing_index(1, 5, 5, 1) == 0.0
    assert wellbeing_index(3, 3, 3, 3) == 50.0


def test_stress_and_calmness_scales() -> None:
    assert stress_index(1) == 0
    assert stress_index(5) == 100
    assert stress_index(1.9) == 22  # screen 05: "22 / 100"
    assert calmness(1.6) == 4.4      # screen 05: "Calmness (4.4 / 5)"


def test_reaction_scoring_follows_vigilance_task_rules() -> None:
    # 18 stimuli: 17 good answers, one very slow (lapse), one tap with no stimulus.
    times = [250.0] * 16 + [300.0, 620.0]
    result = score_reaction_test(times, false_starts=1)
    assert result.trials_total == 18
    assert result.valid_responses == 17
    assert result.lapses == 1
    assert result.false_starts == 1
    assert result.reaction_ms == pytest.approx((250 * 16 + 300 + 620) / 18, abs=0.1)
    assert result.accuracy_pct == pytest.approx(100 * 17 / 19, abs=0.1)
    # Errors over valid stimuli plus false starts (Basner & Dinges 2011).
    assert result.attention_score == pytest.approx(100 * (1 - 2 / 19), abs=0.1)


def test_misses_and_too_early_answers() -> None:
    result = score_reaction_test([None, 80.0, 240.0], false_starts=0)
    assert result.lapses == 1          # no response
    assert result.false_starts == 1    # under 100 ms
    assert result.valid_responses == 1
    assert result.reaction_ms == 240.0
    empty = score_reaction_test([None], false_starts=0)
    assert empty.reaction_ms == 0.0 and empty.attention_score == 0.0


def test_stability_is_share_of_days_in_optimal_zone() -> None:
    assert stability_pct([4.5, 4.0, 3.5, 4.8]) == 75
    assert stability_pct([]) == 0


# -------------------------------------------------------------- database ---

@pytest.fixture()
def conn(temp_db_path: Path):
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with open_connection(temp_db_path) as connection:
        yield connection


def _fresh_crew(conn, crew_id: str) -> str:
    """A crew member with no check-ins (health records are append-only, never deleted)."""
    conn.execute(
        """INSERT INTO crew_members (id, code, full_name, role, pin_hash, is_active,
           created_at_utc, updated_at_utc)
           VALUES (?, ?, 'Test Crew', 'ASTRONAUT', 'x', 1, '2026-01-01T00:00:00Z',
                   '2026-01-01T00:00:00Z')""",
        (crew_id, crew_id.replace("-", "·")),
    )
    return crew_id


def test_old_databases_get_the_new_columns() -> None:
    old = sqlite3.connect(":memory:")
    old.row_factory = sqlite3.Row
    old.execute("CREATE TABLE psych_tests (id INTEGER PRIMARY KEY)")
    old.execute("CREATE TABLE cognitive_tests (id INTEGER PRIMARY KEY)")
    ensure_mind_columns(old)
    ensure_mind_columns(old)  # idempotent
    psych = {r["name"] for r in old.execute("PRAGMA table_info(psych_tests)")}
    cog = {r["name"] for r in old.execute("PRAGMA table_info(cognitive_tests)")}
    assert {"mood_state", "sleep_onset_utc", "wake_utc", "assessment_type", "payload_json"} <= psych
    assert {"trials_total", "valid_responses", "false_starts", "lapses", "payload_json"} <= cog


def test_profile_builds_trend_scales_and_reaction(conn) -> None:
    _fresh_crew(conn, "ID-09")
    for day, (mood, stress) in enumerate([(4, 2), (5, 1), (3, 3)], start=12):
        save_checkin(conn, "ID-09", mood_state="CALM", mood=mood, stress=stress, isolation=1,
                     motivation=5, recorded_at_utc=f"2026-11-{day}T08:00:00Z")
    save_checkin(conn, "ID-09", mood_state="FOCUSED", mood=5, stress=2, isolation=2,
                 motivation=4, sleep_onset_utc="22:18", wake_utc="05:54",
                 recorded_at_utc="2026-11-15T07:45:00Z")
    save_reaction_session(conn, "ID-09", [250.0] * 17 + [None], false_starts=0,
                          recorded_at_utc="2026-11-15T08:00:00Z")

    profile = psych_profile(conn, "ID-09", now=datetime(2026, 11, 15, 12, 0, tzinfo=UTC))
    assert profile["latest_state"]["mood_state"] == "FOCUSED"
    days = [t["day"] for t in profile["trend"]]
    assert days == ["2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15"]
    nov14 = profile["trend"][2]
    assert (nov14["day"], nov14["mood"], nov14["calmness"]) == ("2026-11-14", 3.0, 3.0)
    assert nov14["day_label"]
    assert profile["scales"]["mood"]["value"] == 5.0
    assert profile["scales"]["stress_index"]["value"] == 25
    assert profile["scales"]["isolation"]["label"] == "Low"
    assert profile["stability_pct"] == 75
    reaction = profile["reaction"]
    assert reaction["reaction_ms"] == 250.0
    assert reaction["lapses"] == 1 and reaction["trials_total"] == 18


def test_scale_labels_compare_today_with_earlier_days(conn) -> None:
    _fresh_crew(conn, "ID-10")
    now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)

    def log(day: int, mood: int, motivation: int, stage: str | None = None) -> None:
        if stage:  # a pre-flight check-in, stored with its own stage
            conn.execute(
                """INSERT INTO psych_tests (crew_id, mission_stage, mood_score, stress_score,
                   loneliness_score, motivation_score, wellbeing_index, recorded_at_utc)
                   VALUES ('ID-10', ?, ?, 2, 1, ?, 80, ?)""",
                (stage, mood, motivation, f"2026-11-{day}T08:00:00Z"),
            )
            return
        save_checkin(conn, "ID-10", mood_state=None, mood=mood, stress=2, isolation=1,
                     motivation=motivation, recorded_at_utc=f"2026-11-{day}T08:00:00Z")

    # A first check-in has nothing earlier: it is read against the optimal zone.
    log(12, 3, 4)
    first = psych_profile(conn, "ID-10", now=now)["scales"]
    assert first["mood"]["range_source"] == "OPTIMAL_ZONE"
    assert first["mood"]["label"] == "Low" and first["motivation"]["label"] == "Positive"

    # Later days are read against the days before them, never against themselves.
    log(13, 4, 4)
    log(15, 2, 5)
    recent = psych_profile(conn, "ID-10", now=now)["scales"]
    assert recent["mood"]["range"] == (3.0, 4.0) and recent["mood"]["range_source"] == "RECENT"
    assert recent["mood"]["label"] == "Low"
    assert recent["motivation"]["label"] == "High"

    # Pre-flight check-ins, when they exist, are the personal baseline.
    log(10, 2, 5, stage="LAUNCH")
    baseline = psych_profile(conn, "ID-10", now=now)["scales"]
    assert baseline["mood"]["range"] == (2.0, 2.0)
    assert baseline["mood"]["range_source"] == "BASELINE"
    assert baseline["mood"]["label"] == "Positive"


def test_profile_without_data_is_empty_not_an_error(conn) -> None:
    _fresh_crew(conn, "ID-11")
    profile = psych_profile(conn, "ID-11")
    assert profile["scales"] is None and profile["reaction"] is None
    assert profile["trend"] == [] and profile["stability_pct"] == 0


def test_session_without_valid_answers_has_no_reaction_time(conn) -> None:
    save_reaction_session(conn, "ID-02", [None, None, 700.0], false_starts=2)
    reaction = psych_profile(conn, "ID-02")["reaction"]
    assert reaction["reaction_ms"] is None
    assert reaction["lapses"] == 3 and reaction["false_starts"] == 2


# ------------------------------------------------------------------- API ---

def _headers(client: TestClient, crew_id: str) -> dict[str, str]:
    login = client.post("/api/v1/auth/login", json={"crew_id": crew_id, "pin": PINS[crew_id]})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_api_round_trip_for_signed_in_member(temp_db_path: Path) -> None:
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with TestClient(fastapi_app) as client:
        assert client.get("/api/v1/psych/profile").status_code == 401
        headers = _headers(client, "ID-01")

        checkin = client.post("/api/v1/psych/checkins", headers=headers, json={
            "mood_state": "CALM", "mood": 5, "stress": 2, "isolation": 1, "motivation": 5,
            "sleep_onset_utc": "22:18", "wake_utc": "05:54",
        })
        assert checkin.status_code == 201
        assert checkin.json()["wellbeing_index"] == wellbeing_index(5, 2, 1, 5)

        bad = client.post("/api/v1/psych/checkins", headers=headers, json={
            "mood": 6, "stress": 2, "isolation": 1, "motivation": 5, "wake_utc": "25:00",
        })
        assert bad.status_code == 422

        session = client.post("/api/v1/cognitive/sessions", headers=headers, json={
            "reaction_times_ms": [268.0] * 18, "false_starts": 0,
        })
        assert session.status_code == 201
        assert session.json()["valid_responses"] == 18

        profile = client.get("/api/v1/psych/profile", headers=headers).json()
        assert profile["crew_id"] == "ID-01"
        assert profile["latest_state"]["mood_state"] == "CALM"
        assert profile["reaction"]["reaction_ms"] == 268.0

    with open_connection(temp_db_path) as db:
        row = db.execute(
            "SELECT sleep_onset_utc, wake_utc FROM psych_tests WHERE crew_id = 'ID-01'"
            " ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert (row["sleep_onset_utc"], row["wake_utc"]) == ("22:18", "05:54")


def test_behavioral_matrix_scoring_and_critical_alert(temp_db_path: Path) -> None:
    report = score_behavioral_matrix([3] * 16 + [2] * 4)
    assert report["total_load_score"] == 56
    assert report["readiness_status"] == "RESTRICTED DUTY"
    assert report["subscales"]["T"]["score"] == 12
    assert report["subscales"]["S"]["score"] == 8
    assert report["apa_crosswalk"]["stage2_triggered"] is True

    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with TestClient(fastapi_app) as client:
        headers = _headers(client, "ID-01")
        saved = client.post(
            "/api/v1/psych/checkins",
            headers=headers,
            json={
                "assessment_type": "BEHAVIORAL_MATRIX_20",
                "item_responses": [3] * 16 + [2] * 4,
            },
        )
        assert saved.status_code == 201, saved.text
        data = saved.json()
        assert data["alert_id"] is not None
        assert data["matrix_report"]["total_load_score"] == 56

        profile = client.get("/api/v1/psych/profile", headers=headers).json()
        assert profile["behavioral_matrix"] is not None
        assert profile["behavioral_matrix"]["total_load_score"] == 56
        assert profile["behavioral_matrix"]["readiness_status"] == "RESTRICTED DUTY"

    with open_connection(temp_db_path) as db:
        alert = db.execute(
            "SELECT severity, category FROM alerts WHERE id = ?", (data["alert_id"],)
        ).fetchone()
    assert alert["severity"] == "CRITICAL"
    assert alert["category"] == "PSYCHOSOCIAL"


def test_astrocow_session_and_pilot_alert_escalation(temp_db_path: Path) -> None:
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with TestClient(fastapi_app) as client:
        pilot_headers = _headers(client, "ID-01")
        bad_session = client.post(
            "/api/v1/cognitive/sessions",
            headers=pilot_headers,
            json={
                "test_type": "ASTROCOW_SIM",
                "astrocow": {
                    "score": 14,
                    "high_score": 14,
                    "difficulty_level": 3,
                    "duration_sec": 72,
                    "errors_after_change": 4,
                    "omitted_responses": 2,
                    "collisions": 3,
                    "reticle_hits": 4,
                    "reticle_total": 8,
                    "reaction_times_ms": [440, 480, 520, 460],
                    "recovery_times_sec": [2.1, 2.5, 2.3],
                    "performance_by_minute": [
                        {"minute": 1, "accuracyPct": 50, "targetsHit": 4, "targetsTotal": 8}
                    ],
                },
            },
        )
        assert bad_session.status_code == 201, bad_session.text
        body = bad_session.json()
        assert body["alert_id"] is not None
        assert body["astrocow"]["mean_reaction_ms"] == 475.0
        assert body["astrocow"]["precision_pct"] == 50.0
        assert body["astrocow"]["recovery_time_sec"] == 2.3

        profile = client.get("/api/v1/psych/profile", headers=pilot_headers).json()
        assert profile["crew_role"] == "PILOT"
        assert profile["astrocow"] is not None
        assert profile["astrocow"]["rt_variability_ms"] > 0
        assert len(profile["astrocow_trend"]) >= 1

    with open_connection(temp_db_path) as db:
        alert = db.execute(
            "SELECT severity, message_en FROM alerts WHERE id = ?",
            (body["alert_id"],),
        ).fetchone()
    assert alert["severity"] == "CRITICAL"
    assert "PILOT" in alert["message_en"]


def test_neurofit_session_and_profile_trends(temp_db_path: Path) -> None:
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with TestClient(fastapi_app) as client:
        headers = _headers(client, "ID-01")
        reaction = client.post(
            "/api/v1/cognitive/sessions",
            headers=headers,
            json={"reaction_times_ms": [245.0] * 12, "false_starts": 0},
        )
        assert reaction.status_code == 201

        nf = client.post(
            "/api/v1/cognitive/sessions",
            headers=headers,
            json={
                "test_type": "NEUROFIT_LAB",
                "neurofit": {
                    "copilot_id": "tamalito",
                    "duration_sec": 95,
                    "total_score": 410,
                    "ecg_index": 520,
                    "stages": [
                        {
                            "key": "sequence",
                            "title": "1. Sequence Factory",
                            "cabCode": "CAB-ME",
                            "cabName": "Working Memory",
                            "score": 120,
                            "accuracy": 90,
                            "correct_attempts": 9,
                            "error_attempts": 1,
                            "total_attempts": 10,
                            "avg_reaction_ms": 620,
                            "level_reached": 4,
                            "duration_sec": 30,
                        },
                        {
                            "key": "bee",
                            "title": "2. Color Squad",
                            "cabCode": "CAB-AT",
                            "cabName": "Focused Attention & Inhibition",
                            "score": 110,
                            "accuracy": 80,
                            "correct_attempts": 8,
                            "error_attempts": 2,
                            "total_attempts": 10,
                            "avg_reaction_ms": 740,
                            "level_reached": 3,
                            "duration_sec": 30,
                        },
                        {
                            "key": "explorer",
                            "title": "3. Space Explorer",
                            "cabCode": "CAB-RS",
                            "cabName": "Spatial Reasoning & Planning",
                            "score": 90,
                            "accuracy": 100,
                            "correct_attempts": 2,
                            "error_attempts": 0,
                            "total_attempts": 2,
                            "avg_reaction_ms": 1800,
                            "level_reached": 3,
                            "duration_sec": 15,
                        },
                        {
                            "key": "scan",
                            "title": "4. Rapid Scan",
                            "cabCode": "CAB-PC",
                            "cabName": "Visual Perception & Processing Speed",
                            "score": 90,
                            "accuracy": 90,
                            "correct_attempts": 9,
                            "error_attempts": 1,
                            "total_attempts": 10,
                            "avg_reaction_ms": 840,
                            "level_reached": 3,
                            "duration_sec": 30,
                        },
                    ],
                },
            },
        )
        assert nf.status_code == 201, nf.text
        res = nf.json()
        assert res["neurofit"]["retention_pct"] == 90.0
        assert res["neurofit"]["sustained_attention_pct"] == 85.0
        assert res["neurofit"]["focus_index_score"] >= 85.0

        profile = client.get("/api/v1/psych/profile", headers=headers).json()
        assert profile["reaction"]["reaction_ms"] == 245.0
        assert profile["neurofit"] is not None
        assert profile["neurofit"]["retention_pct"] == 90.0
        assert len(profile["neurofit_trend"]) >= 1
