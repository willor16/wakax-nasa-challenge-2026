"""Delayed ground communications queue and solar weather endpoints (D1-07)."""

import json
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.db import open_connection
from app.services.comms_service import enqueue_daily_summary, process_ground_outbox

router = APIRouter(prefix="/api/v1", tags=["comms"])


class QueuePacketIn(BaseModel):
    crew_id: str | None = Field(default="ID-01")
    packet_type: Literal["DAILY_SUMMARY", "CLINICAL_REPORT"] = "DAILY_SUMMARY"
    note_en: str | None = Field(default=None, max_length=280)


class InboundDirectiveIn(BaseModel):
    crew_id: str | None = Field(default=None)
    title_en: str = Field(..., min_length=2, max_length=120)
    guidance_en: str = Field(..., min_length=4, max_length=500)


def _format_packet(row: dict) -> dict:
    try:
        parsed = json.loads(row["bundle_json"])
    except json.JSONDecodeError:
        parsed = {}

    summary = (
        parsed.get("crew_summary")
        or parsed.get("guidance_en")
        or parsed.get("title_en")
        or "Clinical telemetry packet"
    )
    return {
        "id": row["id"],
        "packet_type": row["packet_type"],
        "direction": row["direction"],
        "crew_id": row["crew_id"],
        "status": row["status"],
        "created_at_utc": row["created_at_utc"],
        "deliver_after_utc": row["deliver_after_utc"],
        "delivered_at_utc": row["delivered_at_utc"],
        "summary": summary,
        "title_en": parsed.get("title_en"),
        "guidance_en": parsed.get("guidance_en"),
    }


@router.get("/comms")
def get_comms_status() -> dict:
    """Return ground transmission queue, flight surgeon directives, and solar telemetry."""
    with open_connection() as conn:
        mission_row = conn.execute(
            "SELECT mission_code, earth_latency_min FROM mission WHERE id = 1"
        ).fetchone()
        outbox_rows = conn.execute(
            """
            SELECT *
            FROM ground_outbox
            WHERE direction = 'OUTBOUND'
            ORDER BY id DESC
            LIMIT 20
            """
        ).fetchall()
        directive_rows = conn.execute(
            """
            SELECT *
            FROM ground_outbox
            WHERE direction = 'INBOUND'
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()
        solar_rows = conn.execute(
            """
            SELECT radiation_msv, solar_event_flag, co2_ppm, recorded_at_utc
            FROM environment_readings
            ORDER BY id DESC
            LIMIT 6
            """
        ).fetchall()

    return {
        "mission_code": mission_row["mission_code"] if mission_row else "ARES VII",
        "earth_latency_min": int(mission_row["earth_latency_min"]) if mission_row else 12,
        "outbound_packets": [_format_packet(dict(r)) for r in outbox_rows],
        "inbound_directives": [_format_packet(dict(r)) for r in directive_rows],
        "solar_weather": [dict(r) for r in solar_rows],
    }


@router.post("/comms/packets", status_code=status.HTTP_201_CREATED)
def queue_outbound_packet(body: QueuePacketIn) -> dict:
    """Enqueue an outbound clinical summary packet with simulated Earth latency."""
    with open_connection() as conn:
        packet = enqueue_daily_summary(
            conn,
            crew_id=body.crew_id,
            packet_type=body.packet_type,
            note_en=body.note_en,
        )
        conn.commit()
    return packet


@router.post("/comms/directives", status_code=status.HTTP_201_CREATED)
def receive_ground_directive(body: InboundDirectiveIn) -> dict:
    """Record an inbound remote flight surgeon directive in ground_outbox."""
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle = {
        "title_en": body.title_en.strip(),
        "guidance_en": body.guidance_en.strip(),
        "received_at_utc": now_iso,
    }
    with open_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO ground_outbox (
                packet_type, direction, crew_id, bundle_json,
                created_at_utc, deliver_after_utc, delivered_at_utc, status
            ) VALUES ('GROUND_DIRECTIVE', 'INBOUND', ?, ?, ?, ?, ?, 'DELIVERED')
            """,
            (body.crew_id, json.dumps(bundle), now_iso, now_iso, now_iso),
        )
        conn.commit()
    return {
        "id": int(cur.lastrowid),
        "packet_type": "GROUND_DIRECTIVE",
        "direction": "INBOUND",
        "status": "DELIVERED",
        **bundle,
    }


@router.post("/comms/flush")
def flush_outbound_queue() -> dict[str, int]:
    """Advance due outbound packets immediately (used by scheduler and verification)."""
    with open_connection() as conn:
        result = process_ground_outbox(conn)
        conn.commit()
    return result
