"""Mission time helpers: mission day numbers, stage and UTC formatting."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def to_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(TS_FORMAT)


def parse_iso(text: str) -> datetime:
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


# Time windows offered by every trend chart (24H · 7D · 14D · 30D · ALL).
PERIOD_HOURS: dict[str, int | None] = {"24h": 24, "7d": 168, "14d": 336, "30d": 720, "all": None}


def period_since(anchor: datetime, period: str) -> str | None:
    """Start (ISO) of a trend window ending at ``anchor``; None for the whole mission."""
    hours = PERIOD_HOURS[period]
    return None if hours is None else to_iso(anchor - timedelta(hours=hours))


def mission_row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM mission WHERE id = 1").fetchone()


def launch_date(conn: sqlite3.Connection) -> date | None:
    row = mission_row(conn)
    return parse_iso(row["launch_utc"]).date() if row else None


def mission_day(conn: sqlite3.Connection, on: date | datetime | None = None) -> int | None:
    """Day number counted from launch day = Day 1 (pre-flight days are <= 0)."""
    start = launch_date(conn)
    if start is None:
        return None
    if on is None:
        on = utc_now().date()
    if isinstance(on, datetime):
        on = on.astimezone(UTC).date()
    return (on - start).days + 1


def day_label(day: int | None) -> str:
    """``D047`` style label used on charts; pre-flight days read ``PRE``."""
    if day is None or day < 1:
        return "PRE"
    return f"D{day:02d}" if day < 100 else f"D{day}"


def date_for_day(conn: sqlite3.Connection, day: int) -> date | None:
    start = launch_date(conn)
    return start + timedelta(days=day - 1) if start else None


def current_stage(conn: sqlite3.Connection) -> str:
    row = mission_row(conn)
    return row["current_stage"] if row else "MISSION"


def mission_elapsed_days(conn: sqlite3.Connection) -> int | None:
    row = mission_row(conn)
    if row is None:
        return None
    return max(0, (utc_now() - parse_iso(row["launch_utc"])).days)
