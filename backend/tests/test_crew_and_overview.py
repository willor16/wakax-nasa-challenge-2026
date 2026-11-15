"""API tests for D1-04 crew administration/baselines and D1-05 crew overview."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.main import app as fastapi_app
from db.seed import seed_database


def test_crew_overview_and_operator_management(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    with TestClient(fastapi_app) as client:
        overview = client.get("/api/v1/crew-overview")
        assert overview.status_code == 200
        body = overview.json()
        assert len(body["crew"]) == 4
        assert 0 <= body["crew_score"] <= 100
        assert body["cabin"]["co2_ppm"] > 0

        pilot_token = client.post(
            "/api/v1/auth/login",
            json={"crew_id": "ID-01", "pin": "1042"},
        ).json()["access_token"]
        denied = client.get("/api/v1/crew", headers={"Authorization": f"Bearer {pilot_token}"})
        assert denied.status_code == 403

        op_token = client.post(
            "/api/v1/auth/login",
            json={"crew_id": "ID-02", "pin": "2084"},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {op_token}"}

        created = client.post(
            "/api/v1/crew",
            headers=headers,
            json={
                "id": "ID-05",
                "code": "ID·05",
                "full_name": "Nadia Solis",
                "role": "ASTRONAUT",
                "pin": "5512",
            },
        )
        assert created.status_code == 201

        patched = client.patch(
            "/api/v1/crew/ID-05",
            headers=headers,
            json={"is_active": False},
        )
        assert patched.status_code == 200
        assert patched.json()["is_active"] == 0

        recomputed = client.post("/api/v1/crew/ID-01/baselines/recompute", headers=headers)
        assert recomputed.status_code == 200
        assert recomputed.json()["updated_count"] >= 15

        ground = client.post(
            "/api/v1/crew/ground-sync",
            json={
                "action": "UPDATE",
                "crew_id": "ID-05",
                "full_name": "Nadia Solis-Vega",
            },
        )
        assert ground.status_code == 202
