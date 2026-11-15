"""Shared Day-1 cross-module contracts for alerts and crew streaks."""

import sqlite3
from datetime import UTC, datetime

from app.config import QUIET_HOURS_END_UTC, QUIET_HOURS_START_UTC
from app.services.alert_engine import evaluate_measurement


def is_within_quiet_hours(timestamp_utc: str) -> bool:
    """Return True if the HH:MM UTC portion falls inside Quiet Hours (22:00-06:00)."""
    parsed = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
    hhmm = parsed.strftime("%H:%M")
    return hhmm >= QUIET_HOURS_START_UTC or hhmm < QUIET_HOURS_END_UTC


def evaluate_alerts(conn: sqlite3.Connection, measurement_id: int) -> list[int]:
    """Evaluate a newly inserted measurement and create alerts (D3-01).

    Day-1 signature kept for the ingestion endpoint. The decision combines the
    catalog limits, the crew member's personal baseline (z-score) and role focus,
    defers non-critical alerts during Quiet Hours and stores three care steps
    plus a medical guide link. Returns the list of created alert IDs.
    """
    return evaluate_measurement(conn, measurement_id)


def update_streaks(conn: sqlite3.Connection, crew_id: str, date_utc: str) -> dict:
    """Increment daily log compliance in streak_days for crew_id on date_utc (YYYY-MM-DD)."""
    day_key = date_utc[:10]
    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    existing = conn.execute(
        "SELECT logs_completed, habits_met FROM streak_days WHERE crew_id = ? AND streak_date_utc = ?",
        (crew_id, day_key),
    ).fetchone()

    if existing is None:
        logs_completed = 1
        habits_met = 0
        daily_compliant = 1
        conn.execute(
            """
            INSERT INTO streak_days (
                crew_id, streak_date_utc, logs_completed, habits_met, daily_compliant, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (crew_id, day_key, logs_completed, habits_met, daily_compliant, now_utc),
        )
    else:
        logs_completed = int(existing["logs_completed"]) + 1
        habits_met = int(existing["habits_met"])
        daily_compliant = 1 if logs_completed >= 1 else 0
        conn.execute(
            """
            UPDATE streak_days
            SET logs_completed = ?, daily_compliant = ?, updated_at_utc = ?
            WHERE crew_id = ? AND streak_date_utc = ?
            """,
            (logs_completed, daily_compliant, now_utc, crew_id, day_key),
        )

    return {
        "crew_id": crew_id,
        "streak_date_utc": day_key,
        "logs_completed": logs_completed,
        "habits_met": bool(habits_met),
        "daily_compliant": bool(daily_compliant),
    }
