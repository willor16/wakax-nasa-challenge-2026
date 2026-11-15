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


@pytest.fixture(scope="session", autouse=True)
def seeded_template(tmp_path_factory: pytest.TempPathFactory):
    """Build the 47-day training mission once; every test database starts as a copy."""
    import os
    import sqlite3

    from db.seed import seed_database

    folder = tmp_path_factory.mktemp("template")
    build_path = folder / "build.db"
    os.environ["SPACESCAN_SENSOR_SIMULATOR"] = "0"
    os.environ.pop("SPACESCAN_SEED_TEMPLATE", None)
    seed_database(db_path=build_path, audio_dir=folder / "audio", with_audio=False)
    template = folder / "template.db"
    with sqlite3.connect(build_path) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM INTO ?", (str(template),))
    os.environ["SPACESCAN_SEED_TEMPLATE"] = str(template)
    yield template
    os.environ.pop("SPACESCAN_SEED_TEMPLATE", None)


PINS = {"ID-01": "1042", "ID-02": "2084", "ID-03": "3190", "ID-04": "4275"}


@pytest.fixture()
def client(temp_db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """API client over a fresh copy of the seeded mission, with audio stored in a temp folder."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import auscultation_service
    from db.seed import seed_database

    seed_database(db_path=temp_db_path, with_audio=False)
    monkeypatch.setattr(auscultation_service, "AUDIO_STORAGE_DIR", tmp_path / "audio")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def login(client):
    """``login("ID-01")`` -> Authorization headers for that crew member."""

    def _login(crew_id: str) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login", json={"crew_id": crew_id, "pin": PINS[crew_id]}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _login


@pytest.fixture()
def db(temp_db_path: Path):
    """Direct connection to a fresh copy of the seeded mission."""
    from app.db import open_connection
    from db.seed import seed_database

    seed_database(db_path=temp_db_path, with_audio=False)
    conn = open_connection(temp_db_path)
    yield conn
    conn.close()
