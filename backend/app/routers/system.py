"""System health, mission metadata, and live Server-Sent Events telemetry."""

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.db import open_connection

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return onboard service and local storage readiness."""
    with open_connection() as conn:
        crew_count = conn.execute("SELECT COUNT(*) FROM crew_members").fetchone()[0]
        mission_row = conn.execute("SELECT mission_code, current_stage FROM mission WHERE id = 1").fetchone()
    return {
        "status": "nominal",
        "mission_code": mission_row["mission_code"] if mission_row else "ARES VII",
        "mission_stage": mission_row["current_stage"] if mission_row else "MISSION",
        "crew_count": str(crew_count),
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@router.get("/mission")
def get_mission_summary() -> dict:
    """Return active mission metadata and latest cabin environment reading."""
    with open_connection() as conn:
        mission_row = conn.execute("SELECT * FROM mission WHERE id = 1").fetchone()
        env_row = conn.execute(
            "SELECT * FROM environment_readings ORDER BY id DESC LIMIT 1"
        ).fetchone()
        active_alerts = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE acknowledged_at_utc IS NULL"
        ).fetchone()[0]
        critical_alerts = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE acknowledged_at_utc IS NULL AND severity = 'CRITICAL'"
        ).fetchone()[0]

    return {
        "mission": dict(mission_row) if mission_row else None,
        "cabin": dict(env_row) if env_row else None,
        "unread_alerts": int(active_alerts),
        "critical_alerts": int(critical_alerts),
        "cabin_mode": "critical" if int(critical_alerts) > 0 else "nominal",
    }


@router.get("/stream/telemetry")
async def stream_telemetry(crew_id: str = Query(default="ID-01")) -> StreamingResponse:
    """Push live vitals and cabin telemetry via Server-Sent Events."""

    async def event_generator():
        while True:
            with open_connection() as conn:
                vital_rows = conn.execute(
                    """
                    SELECT metric_key, value_num, mission_stage, recorded_at_utc
                    FROM measurements
                    WHERE crew_id = ?
                    ORDER BY id DESC
                    LIMIT 8
                    """,
                    (crew_id,),
                ).fetchall()
                cabin_row = conn.execute(
                    """
                    SELECT co2_ppm, noise_dba, temp_c, humidity_pct, radiation_msv, recorded_at_utc
                    FROM environment_readings
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()
                critical_count = conn.execute(
                    "SELECT COUNT(*) FROM alerts WHERE acknowledged_at_utc IS NULL AND severity = 'CRITICAL'"
                ).fetchone()[0]

            vitals_payload = json.dumps([dict(r) for r in vital_rows])
            cabin_payload = json.dumps(
                {
                    "cabin": dict(cabin_row) if cabin_row else None,
                    "cabin_mode": "critical" if int(critical_count) > 0 else "nominal",
                    "server_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
            yield f"event: vitals\ndata: {vitals_payload}\n\n"
            yield f"event: cabin\ndata: {cabin_payload}\n\n"
            await asyncio.sleep(1.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
