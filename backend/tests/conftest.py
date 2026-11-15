"""Shared pytest fixtures using an isolated temporary SQLite database."""

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture()
def temp_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide an isolated temporary database path for tests."""
    db_file = tmp_path / "spacescan_test.db"
    monkeypatch.setenv("SPACESCAN_DB_PATH", str(db_file))
    return db_file
