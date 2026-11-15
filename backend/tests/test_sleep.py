import base64
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.main import app
from db.seed import seed_database


def test_sleep_monitor_periods_and_history_enrichment(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    with TestClient(app) as client:
        for period, expected_nights in (
            ("last_night", 1),
            ("7d", 7),
            ("14d", 14),
            ("30d", 30),
        ):
            res = client.get("/api/v1/sleep/ID-01", params={"period": period})
            assert res.status_code == 200
            body = res.json()
            assert body["crew_id"] == "ID-01"
            assert body["period"] == period
            assert body["nights_analyzed"] == expected_nights
            assert len(body["stage_cards"]) == 4
            assert len(body["lapse_rows"]) == 4
            assert len(body["ribbon_bouts"]) >= 8
            assert len(body["axis_ticks"]) >= 2

        missing_res = client.get("/api/v1/sleep/ID-99")
        assert missing_res.status_code == 404


def test_create_sleep_session_and_regulatory_compliance(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    with TestClient(app) as client:
        post_res = client.post(
            "/api/v1/sleep/sessions",
            json={
                "crew_id": "ID-02",
                "mission_stage": "MISSION",
                "sleep_start_utc": "2026-11-15T22:18:00Z",
                "sleep_end_utc": "2026-11-16T05:54:00Z",
                "deep_min": 94,
                "rem_min": 108,
                "light_min": 230,
                "awake_min": 24,
            },
        )
        assert post_res.status_code == 201
        created = post_res.json()
        assert created["total_sleep_min"] == 432
        assert created["time_in_bed_min"] == 456
        assert created["bouts_inserted"] >= 15

        get_res = client.get("/api/v1/sleep/ID-02", params={"period": "last_night"})
        assert get_res.status_code == 200
        monitor = get_res.json()
        assert monitor["total_sleep_display"] == "7h 12m"
        assert "22:18" in monitor["rest_window_badge"]
        assert "05:54" in monitor["rest_window_badge"]

        invalid_res = client.post(
            "/api/v1/sleep/sessions",
            json={
                "crew_id": "ID-02",
                "mission_stage": "MISSION",
                "sleep_start_utc": "2026-11-16T06:00:00Z",
                "sleep_end_utc": "2026-11-16T05:00:00Z",
            },
        )
        assert invalid_res.status_code == 422

        restricted_terms = [
            base64.b64decode("bmFzYQ==").decode("utf-8"),
            base64.b64decode("Y2hpbmE=").decode("utf-8"),
        ]
        restricted_pattern = re.compile(rf"\b({'|'.join(restricted_terms)})\b", re.IGNORECASE)
        assert not restricted_pattern.search(json.dumps(monitor))
