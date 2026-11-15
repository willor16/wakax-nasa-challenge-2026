"""API tests for D1-06 crew streaks and D1-07 Mission Control comms."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import get_db
from app.main import app as fastapi_app
from db.seed import seed_database


def test_crew_streaks_endpoint(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    with TestClient(fastapi_app) as client:
        resp = client.get("/api/v1/crew-streaks")
        assert resp.status_code == 200
        payload = resp.json()
        assert len(payload["window_dates"]) == 7
        assert len(payload["crew"]) == 4
        assert 0 <= payload["team_compliance_pct"] <= 100
        assert isinstance(payload["eva_shield_ready"], bool)
        for member in payload["crew"]:
            assert len(member["last_7_days"]) == 7
            assert member["active_streak_days"] >= 0
            assert member["best_streak_days"] >= member["active_streak_days"]


def test_comms_queue_flush_and_directives(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    with TestClient(fastapi_app) as client:
        initial = client.get("/api/v1/comms")
        assert initial.status_code == 200
        init_json = initial.json()
        assert init_json["earth_latency_min"] >= 1
        assert len(init_json["solar_weather"]) >= 1

        queued = client.post(
            "/api/v1/comms/packets",
            json={
                "crew_id": "ID-01",
                "packet_type": "DAILY_SUMMARY",
                "note_en": "Nominal hydration and cardiovascular readiness.",
            },
        )
        assert queued.status_code == 201
        packet = queued.json()
        assert packet["status"] == "QUEUED"
        assert packet["direction"] == "OUTBOUND"

        directive = client.post(
            "/api/v1/comms/directives",
            json={
                "crew_id": "ID-01",
                "title_en": "Electrolyte Boost",
                "guidance_en": "Add 250 mL electrolyte solution post-ergometer block.",
            },
        )
        assert directive.status_code == 201
        assert directive.json()["direction"] == "INBOUND"

        past_utc = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        with get_db(temp_db_path) as conn:
            conn.execute(
                "UPDATE ground_outbox SET deliver_after_utc = ? WHERE id = ?",
                (past_utc, packet["id"]),
            )

        flushed = client.post("/api/v1/comms/flush")
        assert flushed.status_code == 200
        assert flushed.json()["delivered"] >= 1

        after = client.get("/api/v1/comms").json()
        statuses = {item["id"]: item["status"] for item in after["outbound_packets"]}
        assert statuses[packet["id"]] == "DELIVERED"
        assert any(d["title_en"] == "Electrolyte Boost" for d in after["inbound_directives"])
