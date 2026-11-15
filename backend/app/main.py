"""FastAPI entrypoint serving API, SSE telemetry, and static SPA on one port."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import AUDIO_STORAGE_DIR, STATIC_SPA_DIR
from app.db import init_db
from app.routers import (
    alerts,
    auscultation,
    auth,
    comms,
    crew,
    diagnosis,
    guide,
    measurements,
    mind,
    profile,
    sleep,
    streaks,
    system,
    vision,
)
from app.services.comms_service import run_outbox_scheduler_tick
from app.services.scheduled_checks import run_scheduled_checks_tick
from app.services.sensor_simulator import run_sensor_tick_job


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize local database, storage paths, and background scheduler."""
    AUDIO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    run_scheduled_checks_tick()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(run_outbox_scheduler_tick, "interval", seconds=15, id="ground_outbox_sync")
    scheduler.add_job(run_scheduled_checks_tick, "interval", minutes=5, id="scheduled_checks")
    # First pattern scan shortly after start-up, then every 6 hours (runs in the background).
    scheduler.add_job(
        diagnosis.run_anomaly_scan_tick,
        "interval",
        hours=6,
        id="anomaly_scan",
        next_run_time=datetime.now(UTC) + timedelta(seconds=20),
    )
    scheduler.add_job(run_sensor_tick_job, "interval", minutes=5, id="sensor_feed")
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="SpaceScan Onboard API",
    version="1.0.0",
    description="Autonomous crew health monitoring API for deep-space habitats.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(auth.router)
app.include_router(crew.router)
app.include_router(profile.router)
app.include_router(sleep.router)
app.include_router(vision.router)
app.include_router(auscultation.router)
app.include_router(measurements.router)
app.include_router(streaks.router)
app.include_router(comms.router)
app.include_router(alerts.router)
app.include_router(mind.router)
app.include_router(guide.router)
app.include_router(diagnosis.router)

class SpaStaticFiles(StaticFiles):
    """Serves the cockpit build; unknown screen paths load the app shell (deep links work)."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        if path.replace("\\", "/").lstrip("/").startswith("api/"):
            raise StarletteHTTPException(status_code=404, detail="Not found.")
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            response = None
        if response is None or response.status_code == 404:
            fallback = "200.html" if (Path(self.directory) / "200.html").exists() else "index.html"
            return await super().get_response(fallback, scope)
        return response


if STATIC_SPA_DIR.exists():
    app.mount("/", SpaStaticFiles(directory=STATIC_SPA_DIR, html=True), name="spa")
