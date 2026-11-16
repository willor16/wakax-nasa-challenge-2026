"""Tests for scheduled health checks (D3-02)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import open_connection
from app.services.alert_rules import QuietHours
from app.services.scheduled_checks import (
    CHECK_PLANS,
    move_out_of_quiet_hours,
    next_due,
    refresh_scheduled_checks,
)
from db.seed import seed_database

QUIET = QuietHours("22:00", "06:00")
# Seeded mission time is 14 Nov 14:00 and the seeded eye exam is due 14 Nov 20:00.
NOW = datetime(2026, 11, 14, 16, 0, tzinfo=UTC)


def at(day: int, hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(2026, 11, day, int(h), int(m), tzinfo=UTC)


@pytest.mark.parametrize(
    ("due", "expected"),
    [
        (at(15, "14:00"), at(15, "14:00")),   # daytime stays
        (at(15, "23:10"), at(16, "07:30")),   # late evening -> next morning
        (at(16, "03:00"), at(16, "07:30")),   # early morning -> same morning
        (at(16, "06:00"), at(16, "06:00")),   # rest period already over
    ],
)
def test_checks_never_fall_inside_quiet_hours(due: datetime, expected: datetime) -> None:
    assert move_out_of_quiet_hours(due, QUIET) == expected


def test_next_due_follows_last_reading_and_is_never_in_the_past() -> None:
    week = timedelta(hours=168)
    assert next_due(at(10, "12:00"), week, NOW, QUIET) == at(17, "12:00")
    assert next_due(at(1, "12:00"), week, NOW, QUIET) == NOW
    assert next_due(None, week, NOW, QUIET) == NOW


@pytest.fixture()
def conn(temp_db_path: Path):
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with open_connection(temp_db_path) as connection:
        yield connection


def _open_checks(conn, crew_id: str) -> dict[str, str]:
    rows = conn.execute(
        "SELECT check_type, due_at_utc FROM scheduled_checks"
        " WHERE crew_id = ? AND status = 'PENDING'",
        (crew_id,),
    ).fetchall()
    return {r["check_type"]: r["due_at_utc"] for r in rows}


CREW = "ID-09"
# Noon of a fixed future day: after every seeded reading and outside Quiet Hours.
LATER = datetime(2027, 3, 1, 12, 0, tzinfo=UTC)


def _fresh_crew(conn) -> None:
    """A crew member without readings; earlier checks are cleared for a clean slate."""
    conn.execute("DELETE FROM scheduled_checks")
    conn.execute(
        """INSERT INTO crew_members (id, code, full_name, role, pin_hash, is_active,
           created_at_utc, updated_at_utc)
           VALUES (?, 'ID·09', 'Test Crew', 'ASTRONAUT', 'x', 1, '2027-01-01T00:00:00Z',
                   '2027-01-01T00:00:00Z')""",
        (CREW,),
    )


def _reading(conn, metric_key: str, value: float, when: datetime) -> None:
    conn.execute(
        """INSERT INTO measurements (crew_id, metric_key, mission_stage, recorded_at_utc,
           value_num) VALUES (?, ?, 'MISSION', ?, ?)""",
        (CREW, metric_key, when.strftime("%Y-%m-%dT%H:%M:%SZ"), value),
    )


def test_refresh_keeps_one_open_check_per_type_and_is_idempotent(conn) -> None:
    _fresh_crew(conn)
    first = refresh_scheduled_checks(conn, LATER)
    open_checks = _open_checks(conn, CREW)
    assert set(open_checks) == {plan.check_type for plan in CHECK_PLANS}
    # Nothing was ever measured, so every check is due right now.
    assert set(open_checks.values()) == {"2027-03-01T12:00:00Z"}
    assert first["created"] == 5 * len(CHECK_PLANS)   # four seeded crew members plus this one

    second = refresh_scheduled_checks(conn, LATER)
    assert second == {"created": 0, "completed": 0, "missed": 0}


def test_new_reading_completes_the_check_and_schedules_the_next(conn) -> None:
    _fresh_crew(conn)
    refresh_scheduled_checks(conn, LATER)
    _reading(conn, "blood_glucose_mg_dl", 92, LATER + timedelta(hours=1))
    result = refresh_scheduled_checks(conn, LATER + timedelta(hours=2))
    assert result["completed"] == 1 and result["created"] == 1
    done = conn.execute(
        "SELECT completed_at_utc FROM scheduled_checks"
        " WHERE crew_id = ? AND check_type = 'GLUCOSE_STRIP' AND status = 'COMPLETED'", (CREW,)
    ).fetchone()
    assert done["completed_at_utc"] == "2027-03-01T13:00:00Z"
    # Lab strips repeat every 72 h after the last lab reading.
    assert _open_checks(conn, CREW)["GLUCOSE_STRIP"] == "2027-03-04T13:00:00Z"


def test_long_overdue_check_is_missed_and_replaced(conn) -> None:
    _fresh_crew(conn)
    refresh_scheduled_checks(conn, LATER)
    result = refresh_scheduled_checks(conn, LATER + timedelta(hours=13))
    assert result["missed"] == 5 * len(CHECK_PLANS)
    missed = conn.execute(
        "SELECT COUNT(*) FROM scheduled_checks WHERE crew_id = ? AND status = 'MISSED'", (CREW,)
    ).fetchone()[0]
    assert missed == len(CHECK_PLANS)
    # 01:00 UTC is inside Quiet Hours: the replacement waits for the morning.
    assert set(_open_checks(conn, CREW).values()) == {"2027-03-02T07:30:00Z"}


def test_check_texts_are_plain_english() -> None:
    for plan in CHECK_PLANS:
        text = plan.title_en + " " + plan.detail_en
        assert text.isascii()
        for jargon in ("FTS", "JSON", "SQL", "API"):
            assert jargon not in text
