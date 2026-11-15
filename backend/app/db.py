"""SQLite 3 connection utilities and schema initialization."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import DB_PATH, SCHEMA_PATH


class ManagedConnection(sqlite3.Connection):
    """Connection that commits (or rolls back) and always closes when used in ``with``."""

    def __exit__(self, exc_type, exc_value, traceback):  # type: ignore[override]
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def resolve_db_path(db_path: Path | None = None) -> Path:
    """Resolve active SQLite database path, honoring SPACESCAN_DB_PATH overrides."""
    if db_path is not None:
        return db_path
    env_override = os.environ.get("SPACESCAN_DB_PATH")
    return Path(env_override) if env_override else DB_PATH


def open_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite 3 connection with WAL, foreign keys, and row mapping enabled.

    Used as ``with open_connection() as conn:`` the connection commits on success,
    rolls back on error and is always closed.
    """
    target = resolve_db_path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, check_same_thread=False, factory=ManagedConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
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


# Columns added after the first release, applied to older databases at start-up.
_LATE_COLUMNS = (
    ("crew_members", "title_en", "TEXT"),
    ("environment_readings", "kp_index", "REAL"),
    ("environment_readings", "location_en", "TEXT NOT NULL DEFAULT 'Habitat A'"),
    ("streak_days", "habits_done", "INTEGER NOT NULL DEFAULT 0"),
    ("streak_days", "habits_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("sleep_sessions", "stages_recorded", "INTEGER NOT NULL DEFAULT 1"),
    ("alerts", "steps_done_json", "TEXT NOT NULL DEFAULT '{}'"),
)


def init_db(db_path: Path | None = None, schema_path: Path = SCHEMA_PATH) -> None:
    """Apply the canonical SQLite schema and clinical catalog idempotently."""
    from app.services.clinical_catalog import ensure_clinical_metrics
    from app.services.diagnosis import ensure_diagnosis_columns
    from app.services.mind import ensure_mind_columns
    from app.services.wiki_seed import ensure_guide_schema, load_medical_guide

    schema_sql = schema_path.read_text(encoding="utf-8")
    with open_connection(db_path) as conn:
        conn.executescript(schema_sql)
        # Databases created by earlier builds get the newer columns once, at start-up.
        for table, column, ddl in _LATE_COLUMNS:
            columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        ensure_guide_schema(conn)
        ensure_diagnosis_columns(conn)
        ensure_mind_columns(conn)
        ensure_clinical_metrics(conn)
        # New protocols from the shipped guide reach existing databases (never overwrites).
        if conn.execute("SELECT COUNT(*) FROM wiki_articles").fetchone()[0]:
            load_medical_guide(conn)
