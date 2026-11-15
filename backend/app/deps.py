import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from app.config import BACKEND_DIR, SCHEMA_PATH
from app.services.clinical_catalog import ensure_clinical_metrics


def resolve_db_path() -> Path:
    env_override = os.environ.get("SPACESCAN_DB_PATH")
    if env_override:
        return Path(env_override)
    return BACKEND_DIR / "db" / "spacescan.db"


def open_request_connection(db_path: Path | None = None) -> sqlite3.Connection:
    target_path = db_path or resolve_db_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")

    table_check = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'metric_catalog'"
    ).fetchone()
    if table_check is None:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)

    if ensure_clinical_metrics(conn) > 0:
        conn.commit()

    return conn


def get_db_conn() -> Iterator[sqlite3.Connection]:
    conn = open_request_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
