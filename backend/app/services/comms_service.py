"""Store-and-forward link with Mission Control: delayed packets in both directions.

Outbound packets wait in the queue, travel for the one-way signal delay, are
delivered, and are confirmed when the answer has had time to travel back.
Inbound messages and remote crew orders become visible (or take effect) only
after their own delay has passed.
"""

import json
import sqlite3
from datetime import timedelta
from typing import Any

from app.config import DEFAULT_EARTH_LATENCY_MIN
from app.db import open_connection
from app.services.crew_metrics import evaluate_crew_readiness
from app.services.environment import cabin_snapshot
from app.services.mission_clock import (
    day_label,
    mission_day,
    mission_row,
    parse_iso,
    to_iso,
    utc_now,
)

DAILY_SUMMARY_HOUR_UTC = 14
PACKET_TITLES = {
    "DAILY_SUMMARY": "Crew Daily Readiness Summary",
    "CLINICAL_REPORT": "Clinical Results Report",
}


def earth_latency_min(conn: sqlite3.Connection) -> int:
    row = mission_row(conn)
    return int(row["earth_latency_min"]) if row else DEFAULT_EARTH_LATENCY_MIN


def _apply_crew_order(conn: sqlite3.Connection, bundle: dict[str, Any], now_iso: str) -> None:
    """Carry out a signed remote crew-management order once its signal has arrived."""
    action, crew_id = bundle.get("action"), bundle.get("crew_id")
    if action == "CREATE":
        conn.execute(
            """INSERT OR IGNORE INTO crew_members (id, code, full_name, role, title_en, pin_hash,
               age, sex, blood_type, height_cm, is_active, created_at_utc, updated_at_utc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                crew_id,
                bundle["code"],
                bundle["full_name"],
                bundle["role"],
                bundle.get("title_en"),
                bundle["pin_hash"],
                bundle.get("age"),
                bundle.get("sex"),
                bundle.get("blood_type"),
                bundle.get("height_cm"),
                now_iso,
                now_iso,
            ),
        )
    elif action == "DEACTIVATE":
        conn.execute(
            "UPDATE crew_members SET is_active = 0, updated_at_utc = ? WHERE id = ?",
            (now_iso, crew_id),
        )
    elif action == "UPDATE":
        for column in ("full_name", "role", "title_en", "pin_hash", "age", "sex", "blood_type",
                       "height_cm"):
            if bundle.get(column) is not None:
                conn.execute(
                    f"UPDATE crew_members SET {column} = ?, updated_at_utc = ? WHERE id = ?",
                    (bundle[column], now_iso, crew_id),
                )


def process_ground_outbox(conn: sqlite3.Connection, now_utc: str | None = None) -> dict[str, int]:
    """Advance every packet according to the signal delay. Returns counts per transition."""
    now_iso = now_utc or to_iso(utc_now())
    latency = timedelta(minutes=earth_latency_min(conn))

    in_transit = conn.execute(
        "UPDATE ground_outbox SET status = 'IN_TRANSIT' "
        "WHERE direction = 'OUTBOUND' AND status = 'QUEUED'"
    ).rowcount
    delivered = conn.execute(
        """UPDATE ground_outbox SET status = 'DELIVERED', delivered_at_utc = deliver_after_utc
           WHERE direction = 'OUTBOUND' AND status = 'IN_TRANSIT' AND deliver_after_utc <= ?""",
        (now_iso,),
    ).rowcount
    # Mission Control's receipt needs one more signal delay to come back.
    confirm_before = to_iso(parse_iso(now_iso) - latency)
    acknowledged = conn.execute(
        """UPDATE ground_outbox SET status = 'ACKNOWLEDGED'
           WHERE direction = 'OUTBOUND' AND status = 'DELIVERED' AND delivered_at_utc <= ?""",
        (confirm_before,),
    ).rowcount

    received = 0
    arrivals = conn.execute(
        """SELECT id, packet_type, bundle_json FROM ground_outbox
           WHERE direction = 'INBOUND' AND status IN ('QUEUED', 'IN_TRANSIT')
             AND deliver_after_utc <= ?""",
        (now_iso,),
    ).fetchall()
    for packet in arrivals:
        final = "DELIVERED"
        if packet["packet_type"] == "CREW_UPDATE":
            _apply_crew_order(conn, json.loads(packet["bundle_json"]), now_iso)
            final = "ACKNOWLEDGED"
        conn.execute(
            "UPDATE ground_outbox SET status = ?, delivered_at_utc = ? WHERE id = ?",
            (final, now_iso, packet["id"]),
        )
        received += 1
    return {
        "in_transit": int(in_transit),
        "delivered": int(delivered),
        "acknowledged": int(acknowledged),
        "received": received,
    }


def build_daily_bundle(conn: sqlite3.Connection, note_en: str | None = None) -> dict[str, Any]:
    """Standard health summary sent to Mission Control: one entry per crew member plus the cabin."""
    mission = mission_row(conn)
    crew = []
    for m in conn.execute(
        "SELECT id, code, full_name, role FROM crew_members WHERE is_active = 1 ORDER BY code"
    ).fetchall():
        readiness = evaluate_crew_readiness(conn, m["id"])
        advisories = conn.execute(
            """SELECT severity, title_en FROM alerts WHERE crew_id = ?
               AND acknowledged_at_utc IS NULL AND severity != 'INFO'
               ORDER BY created_at_utc DESC LIMIT 5""",
            (m["id"],),
        ).fetchall()
        crew.append(
            {
                "crew_id": m["id"],
                "code": m["code"],
                "full_name": m["full_name"],
                "role": m["role"],
                "status": readiness["status"],
                "readiness_score": readiness["readiness_score"],
                "vitals": readiness["vitals"],
                "open_advisories": [dict(a) for a in advisories],
            }
        )
    return {
        "schema": "spacescan.daily_summary.v1",
        "title_en": PACKET_TITLES["DAILY_SUMMARY"],
        "mission_code": mission["mission_code"] if mission else None,
        "mission_stage": mission["current_stage"] if mission else None,
        "mission_day": mission_day(conn),
        "generated_at_utc": to_iso(utc_now()),
        "crew": crew,
        "cabin": cabin_snapshot(conn),
        "note_en": note_en.strip() if note_en and note_en.strip() else None,
    }


def enqueue_packet(
    conn: sqlite3.Connection,
    crew_id: str | None,
    packet_type: str = "DAILY_SUMMARY",
    note_en: str | None = None,
    title_en: str | None = None,
) -> dict[str, Any]:
    """Queue an outbound health packet for delayed delivery to Mission Control."""
    now = utc_now()
    bundle = build_daily_bundle(conn, note_en)
    bundle["title_en"] = title_en or PACKET_TITLES.get(packet_type, "Health Packet")
    if packet_type == "CLINICAL_REPORT":
        bundle["schema"] = "spacescan.clinical_report.v1"
    deliver_after = now + timedelta(minutes=earth_latency_min(conn))
    cursor = conn.execute(
        """INSERT INTO ground_outbox (packet_type, direction, crew_id, bundle_json,
           created_at_utc, deliver_after_utc, status)
           VALUES (?, 'OUTBOUND', ?, ?, ?, ?, 'QUEUED')""",
        (packet_type, crew_id, json.dumps(bundle), to_iso(now), to_iso(deliver_after)),
    )
    return {
        "id": int(cursor.lastrowid),
        "packet_type": packet_type,
        "direction": "OUTBOUND",
        "status": "QUEUED",
        "title_en": bundle["title_en"],
        "created_at_utc": to_iso(now),
        "deliver_after_utc": to_iso(deliver_after),
    }


# Kept under its Day-1 name for callers written against the first contract.
enqueue_daily_summary = enqueue_packet


def queue_scheduled_summary(conn: sqlite3.Connection) -> bool:
    """Queue today's automatic daily summary once, after the midday check-in hour."""
    now = utc_now()
    if now.hour < DAILY_SUMMARY_HOUR_UTC or mission_row(conn) is None:
        return False
    exists = conn.execute(
        """SELECT 1 FROM ground_outbox WHERE packet_type = 'DAILY_SUMMARY'
           AND direction = 'OUTBOUND' AND substr(created_at_utc, 1, 10) = ?""",
        (now.date().isoformat(),),
    ).fetchone()
    if exists:
        return False
    label = day_label(mission_day(conn)).replace("D", "Day ")
    enqueue_packet(
        conn, None, "DAILY_SUMMARY", title_en=f"{PACKET_TITLES['DAILY_SUMMARY']} ({label})"
    )
    return True


def run_outbox_scheduler_tick() -> None:
    """Scheduler job: move packets along the link and queue the daily summary when due."""
    with open_connection() as conn:
        queue_scheduled_summary(conn)
        process_ground_outbox(conn)
