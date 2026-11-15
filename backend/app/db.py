"""SQLite 3 connection utilities and schema initialization."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import DB_PATH, SCHEMA_PATH


def resolve_db_path(db_path: Path | None = None) -> Path:
    """Resolve active SQLite database path, honoring SPACESCAN_DB_PATH overrides."""
    if db_path is not None:
        return db_path
    env_override = os.environ.get("SPACESCAN_DB_PATH")
    return Path(env_override) if env_override else DB_PATH


def open_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite 3 connection with WAL, foreign keys, and row mapping enabled."""
    target = resolve_db_path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def get_db(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context-managed database connection that commits on exit."""
    conn = open_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None, schema_path: Path = SCHEMA_PATH) -> None:
    """Apply the canonical SQLite schema idempotently."""
    schema_sql = schema_path.read_text(encoding="utf-8")
    with open_connection(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()
