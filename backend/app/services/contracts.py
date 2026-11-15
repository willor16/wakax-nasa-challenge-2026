"""Shared Day-1 cross-module contracts for alerts and crew streaks."""

import json
import sqlite3
from datetime import UTC, datetime

from app.config import QUIET_HOURS_END_UTC, QUIET_HOURS_START_UTC


def is_within_quiet_hours(timestamp_utc: str) -> bool:
    """Return True if the HH:MM UTC portion falls inside Quiet Hours (22:00-06:00)."""
    parsed = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
    hhmm = parsed.strftime("%H:%M")
    return hhmm >= QUIET_HOURS_START_UTC or hhmm < QUIET_HOURS_END_UTC


def evaluate_alerts(conn: sqlite3.Connection, measurement_id: int) -> list[int]:
    """Evaluate a newly inserted measurement against metric_catalog thresholds.

    Creates an alert row when the value breaches nominal or critical limits,
    deferring non-critical alerts during Quiet Hours (22:00-06:00 UTC).
    Returns the list of created alert IDs.
    """
    row = conn.execute(
        """
        SELECT
            m.id,
            m.crew_id,
            m.metric_key,
            m.value_num,
            m.recorded_at_utc,
            c.display_name_en,
            c.category,
            c.unit,
            c.nominal_min,
            c.nominal_max,
            c.warning_min,
            c.warning_max,
            c.critical_min,
            c.critical_threshold
        FROM measurements AS m
        JOIN metric_catalog AS c ON c.metric_key = m.metric_key
        WHERE m.id = ?
        """,
        (measurement_id,),
    ).fetchone()

    if row is None or row["value_num"] is None:
        return []

    val = float(row["value_num"])
    severity: str | None = None

    if (row["critical_threshold"] is not None and val >= float(row["critical_threshold"])) or (
        row["critical_min"] is not None and val <= float(row["critical_min"])
    ):
        severity = "CRITICAL"
    elif (row["warning_max"] is not None and val > float(row["warning_max"])) or (
        row["warning_min"] is not None and val < float(row["warning_min"])
    ):
        severity = "WARNING"
    elif val < float(row["nominal_min"]) or val > float(row["nominal_max"]):
        severity = "WARNING"

    if severity is None:
        return []

    quiet_deferred = 1 if (severity != "CRITICAL" and is_within_quiet_hours(row["recorded_at_utc"])) else 0
    direction_label = "Elevated" if val > float(row["nominal_max"]) else "Below Nominal"
    title_en = f"{row['display_name_en']} {direction_label}"
    message_en = (
        f"Measured {val:g} {row['unit']} (nominal range "
        f"{row['nominal_min']:g}-{row['nominal_max']:g} {row['unit']})."
    )
    actions = [
        f"Verify {row['display_name_en'].lower()} reading within 30 minutes.",
        "Review cabin environment and hydration logs.",
        "Consult Medical Guide protocol and notify onboard physician if persistent.",
    ]

    wiki_row = conn.execute(
        """
        SELECT id FROM wiki_articles
        WHERE lower(category_en) LIKE ?
        LIMIT 1
        """,
        (f"%{row['category'].lower()}%",),
    ).fetchone()
    wiki_id = wiki_row["id"] if wiki_row else None

    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = conn.execute(
        """
        INSERT INTO alerts (
            crew_id, measurement_id, severity, category, title_en, message_en,
            recommended_actions_json, wiki_article_id, is_quiet_deferred, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["crew_id"],
            row["id"],
            severity,
            row["category"],
            title_en,
            message_en,
            json.dumps(actions),
            wiki_id,
            quiet_deferred,
            now_utc,
        ),
    )
    return [int(cursor.lastrowid)]


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
