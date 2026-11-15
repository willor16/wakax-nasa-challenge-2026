"""Scheduled health checks (D3-02): routine reminders kept in ``scheduled_checks``.

A background job keeps exactly one open check per crew member and check type:
* the next check is due one interval after the last reading of that kind
  (interval = shortest ``recommended_frequency_hours`` in that catalog category);
* a check that would fall inside Quiet Hours moves to the morning after them;
* a new reading of that kind after the check was created marks it COMPLETED;
* a check left open long after its due time is marked MISSED and a new one starts.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db import open_connection
from app.services.alert_engine import load_quiet_hours
from app.services.alert_rules import QuietHours, is_quiet_hours, parse_utc

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
# Checks pushed out of Quiet Hours start 90 minutes after the rest period ends,
# leaving time to wake up and eat (screen 16 shows "Tomorrow 07:30 UTC").
MORNING_OFFSET = timedelta(minutes=90)
MISSED_AFTER = timedelta(hours=12)


@dataclass(frozen=True, slots=True)
class CheckPlan:
    check_type: str
    category: str
    title_en: str
    detail_en: str
    fallback_hours: float


CHECK_PLANS: tuple[CheckPlan, ...] = (
    CheckPlan("VITALS_CHECK", "VITALS", "Vital signs check",
              "Heart rate, blood pressure, oxygen and temperature.", 24.0),
    CheckPlan("HABITS_LOG", "HABITS", "Daily habits log",
              "Fluids, exercise minutes and meals.", 24.0),
    CheckPlan("GLUCOSE_STRIP", "LABS", "Blood glucose strip",
              "Finger test before the morning meal.", 72.0),
    CheckPlan("OCULAR_EXAM", "VISION", "Weekly eye scan",
              "Both eyes with the 3.0 mm guide, plus eye pressure.", 168.0),
    CheckPlan("BODY_COMPOSITION", "BIOMETRICS", "Weekly body composition",
              "Body mass, muscle and bone readings.", 168.0),
    CheckPlan("AEROBIC_TEST", "RESPIRATORY", "Aerobic capacity test",
              "Cycle test at steady effort.", 336.0),
)
PLAN_BY_TYPE = {plan.check_type: plan for plan in CHECK_PLANS}


def _ts(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(TS_FORMAT)


def move_out_of_quiet_hours(due: datetime, quiet: QuietHours) -> datetime:
    """Return ``due`` unchanged, or the next morning slot if it falls in Quiet Hours."""
    if not is_quiet_hours(due, quiet):
        return due
    end_h, end_m = (int(part) for part in quiet.end_utc.split(":"))
    end_today = due.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    wake = end_today if due < end_today else end_today + timedelta(days=1)
    return wake + MORNING_OFFSET


def next_due(last_reading: datetime | None, interval: timedelta, now: datetime,
             quiet: QuietHours) -> datetime:
    """Due time for the next check: one interval after the last reading, never in the past."""
    due = (last_reading + interval) if last_reading else now
    return move_out_of_quiet_hours(max(due, now), quiet)


def _interval(conn: sqlite3.Connection, plan: CheckPlan) -> timedelta:
    row = conn.execute(
        "SELECT MIN(recommended_frequency_hours) AS h FROM metric_catalog WHERE category = ?",
        (plan.category,),
    ).fetchone()
    hours = row["h"] if row and row["h"] else plan.fallback_hours
    return timedelta(hours=max(float(hours), plan.fallback_hours))


def _last_reading(conn: sqlite3.Connection, crew_id: str, category: str) -> str | None:
    row = conn.execute(
        """
        SELECT MAX(m.recorded_at_utc) AS last_utc
        FROM measurements AS m
        JOIN metric_catalog AS c ON c.metric_key = m.metric_key
        WHERE m.crew_id = ? AND c.category = ?
        """,
        (crew_id, category),
    ).fetchone()
    return row["last_utc"] if row else None


def refresh_scheduled_checks(conn: sqlite3.Connection, now: datetime | None = None) -> dict:
    """Complete, miss and create checks so each crew member has one open check per type."""
    now = (now or datetime.now(UTC)).replace(microsecond=0)
    now_utc = _ts(now)
    quiet = load_quiet_hours(conn)
    counts = {"created": 0, "completed": 0, "missed": 0}
    crew_ids = [r["id"] for r in conn.execute("SELECT id FROM crew_members WHERE is_active = 1")]

    for crew_id in crew_ids:
        for plan in CHECK_PLANS:
            last_utc = _last_reading(conn, crew_id, plan.category)
            open_check = conn.execute(
                """
                SELECT id, due_at_utc, created_at_utc FROM scheduled_checks
                WHERE crew_id = ? AND check_type = ? AND status IN ('PENDING', 'DEFERRED')
                ORDER BY due_at_utc LIMIT 1
                """,
                (crew_id, plan.check_type),
            ).fetchone()

            if open_check is not None:
                if last_utc and last_utc > open_check["created_at_utc"]:
                    conn.execute(
                        "UPDATE scheduled_checks SET status = 'COMPLETED', completed_at_utc = ?"
                        " WHERE id = ?",
                        (last_utc, open_check["id"]),
                    )
                    counts["completed"] += 1
                elif parse_utc(open_check["due_at_utc"]) + MISSED_AFTER < now:
                    conn.execute(
                        "UPDATE scheduled_checks SET status = 'MISSED' WHERE id = ?",
                        (open_check["id"],),
                    )
                    counts["missed"] += 1
                else:
                    continue

            last = parse_utc(last_utc) if last_utc else None
            due = next_due(last, _interval(conn, plan), now, quiet)
            conn.execute(
                """
                INSERT INTO scheduled_checks (
                    crew_id, check_type, title_en, due_at_utc, status, created_at_utc
                ) VALUES (?, ?, ?, ?, 'PENDING', ?)
                """,
                (crew_id, plan.check_type, plan.title_en, _ts(due), now_utc),
            )
            counts["created"] += 1
    return counts


def run_scheduled_checks_tick() -> None:
    """APScheduler job entrypoint."""
    with open_connection() as conn:
        refresh_scheduled_checks(conn)
        conn.commit()
