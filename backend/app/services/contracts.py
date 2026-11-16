"""Shared Day-1 cross-module contracts for alerts and crew streaks."""

import sqlite3
from datetime import datetime

from app.config import QUIET_HOURS_END_UTC, QUIET_HOURS_START_UTC
from app.services.alert_engine import evaluate_measurement
from app.services.habits import recompute_day


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
    """Recompute the day's habits and streak entry for ``crew_id`` (``YYYY-MM-DD``)."""
    summary = recompute_day(conn, crew_id, date_utc[:10])
    return {
        "crew_id": crew_id,
        "streak_date_utc": summary["date_utc"],
        "logs_completed": summary["logs_completed"],
        "habits_met": summary["habits_done"] == 4,
        "daily_compliant": summary["daily_compliant"],
    }
