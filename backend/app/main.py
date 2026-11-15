"""FastAPI entrypoint serving API, SSE telemetry, and static SPA on one port."""

from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import AUDIO_STORAGE_DIR, STATIC_SPA_DIR
from app.db import init_db
from app.routers import (
    alerts,
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
)
from app.services.comms_service import run_outbox_scheduler_tick
from app.services.scheduled_checks import run_scheduled_checks_tick


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize local database, storage paths, and background scheduler."""
    AUDIO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    run_scheduled_checks_tick()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(run_outbox_scheduler_tick, "interval", seconds=15, id="ground_outbox_sync")
    scheduler.add_job(run_scheduled_checks_tick, "interval", minutes=5, id="scheduled_checks")
    scheduler.add_job(diagnosis.run_anomaly_scan_tick, "interval", hours=6, id="anomaly_scan")
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
app.include_router(measurements.router)
app.include_router(streaks.router)
app.include_router(comms.router)
app.include_router(alerts.router)
app.include_router(mind.router)
app.include_router(guide.router)
app.include_router(diagnosis.router)

if STATIC_SPA_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_SPA_DIR, html=True), name="spa")
