"""API tests for D1-03 PIN authentication and D2-01 measurement ingestion."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.main import app as fastapi_app
from db.seed import seed_database


def test_pin_login_and_measurement_ingestion(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    with TestClient(fastapi_app) as client:
        profiles = client.get("/api/v1/crew/profiles")
        assert profiles.status_code == 200
        assert len(profiles.json()) == 4

        bad_login = client.post("/api/v1/auth/login", json={"crew_id": "ID-01", "pin": "9999"})
        assert bad_login.status_code == 401

        ok_login = client.post("/api/v1/auth/login", json={"crew_id": "ID-01", "pin": "1042"})
        assert ok_login.status_code == 200
        token = ok_login.json()["access_token"]

        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["id"] == "ID-01"

        catalog = client.get("/api/v1/metrics/catalog", params={"category": "VISION"})
        assert catalog.status_code == 200
        assert len(catalog.json()) == 4

        ingest = client.post(
            "/api/v1/measurements",
            json={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "source_type": "MANUAL",
                "items": [
                    {"metric_key": "optic_sheath_left_mm", "value_num": 4.4},
                    {"metric_key": "optic_sheath_right_mm", "value_num": 5.9},
                ],
            },
        )
        assert ingest.status_code == 201
        payload = ingest.json()
        assert len(payload["inserted_ids"]) == 2
        assert len(payload["alerts_created"]) == 1
        assert payload["streak"]["daily_compliant"] is True
