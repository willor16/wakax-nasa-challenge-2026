"""Foundation tests for Phase 0 schema and Phase 1 D1-01 seeder and contracts."""

import sqlite3
from pathlib import Path

import pytest

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import open_connection
from app.services.contracts import evaluate_alerts, is_within_quiet_hours, update_streaks
from db.seed import seed_database


def test_seed_is_idempotent(temp_db_path: Path) -> None:
    first = seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )
    second = seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )
    assert first["crew_members"] == 4
    assert first == second


def test_measurements_append_only_triggers(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )
    with open_connection(temp_db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE measurements SET value_num = 0 WHERE id = 1")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM measurements WHERE id = 1")


def test_wiki_fts5_search_works(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )
    with open_connection(temp_db_path) as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.drawer_code
            FROM wiki_articles_fts AS f
            JOIN wiki_articles AS a ON a.rowid = f.rowid
            WHERE wiki_articles_fts MATCH 'optic'
            """
        ).fetchall()
    assert len(rows) >= 1
    assert rows[0]["drawer_code"] == "DRAWER B2"


def test_evaluate_alerts_quiet_hours_and_streaks(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )
    assert is_within_quiet_hours("2026-11-14T23:30:00Z") is True
    assert is_within_quiet_hours("2026-11-14T14:00:00Z") is False

    with open_connection(temp_db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO measurements (
                crew_id, metric_key, mission_stage, source_type, recorded_at_utc, value_num
            ) VALUES ('ID-01', 'optic_sheath_right_mm', 'MISSION', 'MANUAL', '2026-11-14T23:30:00Z', 5.2)
            """
        )
        created = evaluate_alerts(conn, int(cur.lastrowid))
        assert len(created) == 1
        alert = conn.execute("SELECT severity, is_quiet_deferred FROM alerts WHERE id = ?", (created[0],)).fetchone()
        assert alert["severity"] == "WARNING"
        assert alert["is_quiet_deferred"] == 1

        streak = update_streaks(conn, "ID-01", "2026-11-14T23:30:00Z")
        assert streak["logs_completed"] >= 1
        assert streak["daily_compliant"] is True
