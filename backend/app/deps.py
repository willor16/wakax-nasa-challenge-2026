"""Per-request database dependency for FastAPI routers."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from app.db import open_connection, resolve_db_path

_initialized_paths: set[Path] = set()


def open_request_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a request connection, applying schema and catalog once per database file."""
    target_path = resolve_db_path(db_path)
    if target_path not in _initialized_paths or not target_path.exists():
        from app.db import init_db

        init_db(target_path)
        _initialized_paths.add(target_path)
    return open_connection(target_path)


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
