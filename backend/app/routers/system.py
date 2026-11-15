"""System health, mission summary, cabin environment and live event streams."""

import asyncio
import json
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth_utils import STREAM_SCOPE, CurrentCrew, decode_access_token, verify_session_claims
from app.db import open_connection
from app.services.environment import cabin_mode, cabin_snapshot, record_reading
from app.services.mission_clock import mission_day, to_iso, utc_now

router = APIRouter(prefix="/api/v1", tags=["system"])

STREAM_INTERVAL_SEC = 2.0
# Streams end after a few minutes and the browser reconnects on its own, so a server
# restart or update never waits on a stream that would otherwise stay open forever.
STREAM_LIFETIME_SEC = 300.0


class EnvironmentReadingIn(BaseModel):
    """One cabin sensor reading (sent by the habitat sensors or logged by the crew)."""

    co2_ppm: float = Field(..., ge=0, le=50_000)
    noise_dba: float = Field(..., ge=0, le=140)
    temp_c: float = Field(..., ge=-10, le=60)
    humidity_pct: float = Field(..., ge=0, le=100)
    radiation_msv: float = Field(default=0.0, ge=0, le=1000)
    kp_index: float | None = Field(default=None, ge=0, le=9)
    solar_event: bool = False
    location_en: str | None = Field(default=None, max_length=40)


@router.get("/health")
def health_check() -> dict[str, str]:
    """Onboard service readiness."""
    with open_connection() as conn:
        crew_count = conn.execute("SELECT COUNT(*) FROM crew_members").fetchone()[0]
        mission = conn.execute(
            "SELECT mission_code, current_stage FROM mission WHERE id = 1"
        ).fetchone()
    return {
        "status": "nominal",
        "mission_code": mission["mission_code"] if mission else "",
        "mission_stage": mission["current_stage"] if mission else "",
        "crew_count": str(crew_count),
        "timestamp_utc": to_iso(utc_now()),
    }


@router.get("/mission")
def get_mission_summary() -> dict:
    """Public mission clock data and the latest cabin reading (no personal health data)."""
    with open_connection() as conn:
        mission = conn.execute("SELECT * FROM mission WHERE id = 1").fetchone()
        return {
            "mission": dict(mission) if mission else None,
            "mission_day": mission_day(conn),
            "cabin": cabin_snapshot(conn),
            "cabin_mode": cabin_mode(conn),
            "server_utc": to_iso(utc_now()),
        }


@router.post("/environment", status_code=status.HTTP_201_CREATED)
def post_environment_reading(body: EnvironmentReadingIn, _claims: CurrentCrew) -> dict:
    """Store a cabin reading; values outside the reference limits raise crew advisories."""
    with open_connection() as conn:
        return record_reading(conn, body.model_dump())


def _sse(event: str, payload: dict | list) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


async def _keep_streaming(request: Request, started: float) -> bool:
    if await request.is_disconnected():
        return False
    return time.monotonic() - started < STREAM_LIFETIME_SEC


@router.get("/stream/telemetry")
async def stream_cabin_telemetry(request: Request) -> StreamingResponse:
    """Public live stream: cabin environment and cabin mode only."""

    async def event_generator():
        started = time.monotonic()
        yield "retry: 2000\n\n"
        while await _keep_streaming(request, started):
            with open_connection() as conn:
                payload = {
                    "cabin": cabin_snapshot(conn),
                    "cabin_mode": cabin_mode(conn),
                    "mission_day": mission_day(conn),
                    "server_utc": to_iso(utc_now()),
                }
            yield _sse("cabin", payload)
            await asyncio.sleep(STREAM_INTERVAL_SEC)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/stream/vitals")
async def stream_crew_vitals(
    request: Request, token: Annotated[str, Query(min_length=10)]
) -> StreamingResponse:
    """Private live stream of the signed-in crew member's own latest readings and alert count."""
    claims = verify_session_claims(decode_access_token(token, scope=STREAM_SCOPE))
    crew_id = claims["sub"]
    if not crew_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in with your crew PIN.")

    async def event_generator():
        started = time.monotonic()
        while await _keep_streaming(request, started):
            with open_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT m.metric_key, m.value_num, m.recorded_at_utc FROM measurements AS m
                    JOIN (SELECT metric_key, MAX(id) AS id FROM measurements
                          WHERE crew_id = ? GROUP BY metric_key) AS latest ON latest.id = m.id
                    """,
                    (crew_id,),
                ).fetchall()
                unread = conn.execute(
                    "SELECT COUNT(*) FROM alerts WHERE crew_id = ? AND acknowledged_at_utc IS NULL",
                    (crew_id,),
                ).fetchone()[0]
            yield _sse("vitals", {
                "readings": {r["metric_key"]: {"value": r["value_num"], "at": r["recorded_at_utc"]}
                             for r in rows},
                "unread_alerts": int(unread),
                "server_utc": to_iso(utc_now()),
            })
            await asyncio.sleep(STREAM_INTERVAL_SEC)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
