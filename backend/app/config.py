"""Application paths and onboard runtime configuration."""

import os
import secrets
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

DB_PATH = Path(os.environ.get("SPACESCAN_DB_PATH", BACKEND_DIR / "db" / "spacescan.db"))
SCHEMA_PATH = BACKEND_DIR / "db" / "schema.sql"
SEED_SNAPSHOT_PATH = BACKEND_DIR / "db" / "seed_snapshots" / "mission_baseline.json"
AUDIO_STORAGE_DIR = BACKEND_DIR / "storage" / "audio"
STATIC_SPA_DIR = REPO_ROOT / "frontend" / ".output" / "public"

SESSION_KEY_PATH = Path(
    os.environ.get("SPACESCAN_SESSION_KEY_PATH", BACKEND_DIR / "storage" / "session_signing.key")
)


def _load_or_create_key(path: Path, env_name: str) -> str:
    env_key = os.environ.get(env_name)
    if env_key:
        return env_key
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(48)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(key)
    return key


JWT_SECRET = _load_or_create_key(SESSION_KEY_PATH, "SPACESCAN_JWT_SECRET")
# Shared with Mission Control before launch; signs every remote crew-management order.
GROUND_LINK_KEY_PATH = Path(
    os.environ.get("SPACESCAN_GROUND_KEY_PATH", BACKEND_DIR / "storage" / "ground_link.key")
)
GROUND_LINK_KEY = _load_or_create_key(GROUND_LINK_KEY_PATH, "SPACESCAN_GROUND_LINK_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 480

QUIET_HOURS_START_UTC = "22:00"
QUIET_HOURS_END_UTC = "06:00"
DEFAULT_EARTH_LATENCY_MIN = 12
