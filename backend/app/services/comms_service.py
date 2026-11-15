"""Store-and-forward ground communications queue and packet builder services."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import DEFAULT_EARTH_LATENCY_MIN
from app.db import open_connection


def process_ground_outbox(conn: sqlite3.Connection, now_utc: str | None = None) -> dict[str, int]:
    """Advance queued and in-transit packets based on simulated Earth transmission latency."""
    current_iso = now_utc or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    delivered_cur = conn.execute(
        """
        UPDATE ground_outbox
        SET status = 'DELIVERED', delivered_at_utc = ?
        WHERE direction = 'OUTBOUND'
          AND status IN ('QUEUED', 'IN_TRANSIT')
          AND deliver_after_utc <= ?
        """,
        (current_iso, current_iso),
    )

    transit_cur = conn.execute(
        """
        UPDATE ground_outbox
        SET status = 'IN_TRANSIT'
        WHERE direction = 'OUTBOUND'
          AND status = 'QUEUED'
          AND deliver_after_utc > ?
        """,
        (current_iso,),
    )
    return {
        "delivered": int(delivered_cur.rowcount),
        "in_transit": int(transit_cur.rowcount),
    }


def run_outbox_scheduler_tick() -> None:
    """APScheduler job entrypoint advancing delayed ground transmission packets."""
    with open_connection() as conn:
        process_ground_outbox(conn)
        conn.commit()


def enqueue_daily_summary(
    conn: sqlite3.Connection,
    crew_id: str | None,
    packet_type: str = "DAILY_SUMMARY",
    note_en: str | None = None,
) -> dict[str, Any]:
    """Build a compact clinical bundle and enqueue it for delayed Earth delivery."""
    now = datetime.now(UTC)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    mission_row = conn.execute(
        "SELECT mission_code, current_stage, earth_latency_min FROM mission WHERE id = 1"
    ).fetchone()
    latency_min = int(mission_row["earth_latency_min"]) if mission_row else DEFAULT_EARTH_LATENCY_MIN
    deliver_after_iso = (now + timedelta(minutes=latency_min)).strftime("%Y-%m-%dT%H:%M:%SZ")

    active_alerts = conn.execute(
        "SELECT COUNT(*) FROM alerts WHERE acknowledged_at_utc IS NULL"
    ).fetchone()[0]
    measurement_count = conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]

    bundle = {
        "mission_code": mission_row["mission_code"] if mission_row else "ARES VII",
        "mission_stage": mission_row["current_stage"] if mission_row else "MISSION",
        "generated_at_utc": now_iso,
        "unread_alerts": int(active_alerts),
        "total_measurements": int(measurement_count),
        "crew_summary": note_en.strip()
        if note_en and note_en.strip()
        else f"Routine health packet queued ({int(active_alerts)} active alerts).",
    }

    cursor = conn.execute(
        """
        INSERT INTO ground_outbox (
            packet_type, direction, crew_id, bundle_json,
            created_at_utc, deliver_after_utc, status
        ) VALUES (?, 'OUTBOUND', ?, ?, ?, ?, 'QUEUED')
        """,
        (packet_type, crew_id, json.dumps(bundle), now_iso, deliver_after_iso),
    )

    return {
        "id": int(cursor.lastrowid),
        "packet_type": packet_type,
        "direction": "OUTBOUND",
        "crew_id": crew_id,
        "status": "QUEUED",
        "created_at_utc": now_iso,
        "deliver_after_utc": deliver_after_iso,
        "summary": bundle["crew_summary"],
    }
