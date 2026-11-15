"""System health, mission summary, cabin environment and live event streams."""

import asyncio
import json
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth_utils import (
    STREAM_SCOPE,
    CurrentCrew,
    decode_access_token,
    ensure_crew_access,
    verify_session_claims,
)
from app.db import open_connection
from app.services import change_feed, live_sensor
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


# Live streams must reach every cabin display at once: no caching, no compression and no
# buffering by any proxy in between (the cockpit dev server, a LAN proxy).
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse_response(generator) -> StreamingResponse:
    return StreamingResponse(generator, media_type="text/event-stream", headers=SSE_HEADERS)


def _stream_claims(token: str) -> dict:
    claims = verify_session_claims(decode_access_token(token, scope=STREAM_SCOPE))
    if not claims["sub"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in with your crew PIN.")
    return claims


async def _keep_streaming(request: Request, started: float) -> bool:
    if await request.is_disconnected():
        return False
    return time.monotonic() - started < STREAM_LIFETIME_SEC


@router.get("/stream/telemetry")
async def stream_cabin_telemetry(request: Request) -> StreamingResponse:
    """Public live stream: cabin environment, cabin mode and which kinds of data changed.

    The ``sync`` event names data domains only (never crew values), so it stays public.
    """

    async def event_generator():
        started = time.monotonic()
        seen = change_feed.current()
        yield "retry: 2000\n\n"
        while await _keep_streaming(request, started):
            seen, changed = change_feed.changes_since(seen)
            if changed:
                yield _sse("sync", {"domains": changed})
            with open_connection() as conn:
                payload = {
                    "cabin": cabin_snapshot(conn),
                    "cabin_mode": cabin_mode(conn),
                    "mission_day": mission_day(conn),
                    "server_utc": to_iso(utc_now()),
                }
            yield _sse("cabin", payload)
            await asyncio.sleep(STREAM_INTERVAL_SEC)

    return _sse_response(event_generator())


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

    return _sse_response(event_generator())


@router.get("/stream/live-ecg")
async def stream_live_ecg(
    request: Request, token: Annotated[str, Query(min_length=10)]
) -> StreamingResponse:
    """Private live sensor: continuous Lead II ECG (4 frames/s) and core temperature.

    The waveform follows the crew member's latest real heart rate, heart-rate variability
    and temperature, re-read every two seconds, so a new reading shows up straight away.
    """
    crew_id = _stream_claims(token)["sub"]
    with open_connection() as conn:
        values, override = live_sensor.sensor_inputs(conn, crew_id)
    generator_state = live_sensor.LiveEcg(seed=int(time.time()))
    generator_state.update(values["resting_hr_bpm"], values["hrv_rmssd_ms"], values["body_temp_c"])

    async def event_generator():
        nonlocal override
        started = time.monotonic()
        next_frame = time.monotonic()
        refreshed = time.monotonic()
        yield "retry: 1000\n\n"
        while await _keep_streaming(request, started):
            if time.monotonic() - refreshed >= live_sensor.REFRESH_SECONDS:
                refreshed = time.monotonic()
                with open_connection() as conn:
                    values, override = live_sensor.sensor_inputs(conn, crew_id)
                generator_state.update(
                    values["resting_hr_bpm"], values["hrv_rmssd_ms"], values["body_temp_c"]
                )
            frame = generator_state.frame()
            frame["override_en"] = override
            frame["server_utc"] = to_iso(utc_now())
            yield _sse("ecg", frame)
            next_frame += live_sensor.FRAME_SECONDS
            await asyncio.sleep(max(0.0, next_frame - time.monotonic()))

    return _sse_response(event_generator())


class SensorSimulateIn(BaseModel):
    """Temporary sensor condition for demonstrations and tests (never stored as a reading)."""

    crew_id: str | None = Field(default=None, max_length=32)
    heart_rate_bpm: float | None = Field(default=None, ge=30, le=220)
    body_temp_c: float | None = Field(default=None, ge=34, le=42)
    hrv_rmssd_ms: float | None = Field(default=None, ge=2, le=200)
    duration_s: float = Field(default=120, ge=10, le=600)
    clear: bool = False


@router.post("/sensors/simulate")
def simulate_sensor(body: SensorSimulateIn, claims: CurrentCrew) -> dict:
    """Inject (or clear) a temporary condition on the live sensor, e.g. tachycardia or fever."""
    crew_id = body.crew_id or claims["sub"]
    ensure_crew_access(claims, crew_id)
    if body.clear:
        live_sensor.clear_override(crew_id)
        return {"crew_id": crew_id, "active": False}
    parts = []
    if body.heart_rate_bpm is not None:
        parts.append(f"heart rate {body.heart_rate_bpm:g} bpm")
    if body.body_temp_c is not None:
        parts.append(f"temperature {body.body_temp_c:g} °C")
    if body.hrv_rmssd_ms is not None:
        parts.append(f"HRV {body.hrv_rmssd_ms:g} ms")
    if not parts:
        raise HTTPException(422, "Give a heart rate, temperature or HRV to simulate.")
    live_sensor.set_override(
        crew_id,
        heart_rate_bpm=body.heart_rate_bpm,
        body_temp_c=body.body_temp_c,
        hrv_rmssd_ms=body.hrv_rmssd_ms,
        duration_s=body.duration_s,
        label_en="Simulated sensor: " + ", ".join(parts),
    )
    return {"crew_id": crew_id, "active": True, "duration_s": body.duration_s}
