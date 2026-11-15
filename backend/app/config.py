"""Application paths and onboard runtime configuration."""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

DB_PATH = Path(os.environ.get("SPACESCAN_DB_PATH", BACKEND_DIR / "db" / "spacescan.db"))
SCHEMA_PATH = BACKEND_DIR / "db" / "schema.sql"
SEED_SNAPSHOT_PATH = BACKEND_DIR / "db" / "seed_snapshots" / "mission_baseline.json"
AUDIO_STORAGE_DIR = BACKEND_DIR / "storage" / "audio"
STATIC_SPA_DIR = REPO_ROOT / "frontend" / ".output" / "public"

JWT_SECRET = os.environ.get("SPACESCAN_JWT_SECRET", "ares-vii-onboard-local-signing-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 480

QUIET_HOURS_START_UTC = "22:00"
QUIET_HOURS_END_UTC = "06:00"
DEFAULT_EARTH_LATENCY_MIN = 12
