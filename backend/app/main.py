"""FastAPI entrypoint serving API, SSE telemetry, and static SPA on one port."""

from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import AUDIO_STORAGE_DIR, STATIC_SPA_DIR
from app.db import init_db
from app.routers import auth, comms, crew, measurements, streaks, system
from app.services.comms_service import run_outbox_scheduler_tick


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize local database, storage paths, and background scheduler."""
    AUDIO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(run_outbox_scheduler_tick, "interval", seconds=15, id="ground_outbox_sync")
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
app.include_router(measurements.router)
app.include_router(streaks.router)
app.include_router(comms.router)

if STATIC_SPA_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_SPA_DIR, html=True), name="spa")
