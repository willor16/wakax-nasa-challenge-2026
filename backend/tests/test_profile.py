import base64
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.main import app
from db.seed import seed_database


def test_crew_profile_across_stages_and_crew_members(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    with TestClient(app) as client:
        for crew_id in ("ID-01", "ID-02", "ID-03", "ID-04"):
            res = client.get(f"/api/v1/crew/{crew_id}/profile")
            assert res.status_code == 200
            body = res.json()
            assert body["crew"]["id"] == crew_id
            assert len(body["biometrics"]) == 6
            assert len(body["environment_work"]["gauges"]) == 4
            assert len(body["environment_work"]["work_rows"]) == 3
            assert len(body["daily_vitals"]["items"]) == 6
            assert len(body["live_ecg"]["samples_mv"]) >= 200
            assert len(body["clinical_labs"]) == 4
            assert len(body["stage_comparison"]) == 3

        launch_res = client.get("/api/v1/crew/ID-01/profile", params={"stage": "LAUNCH"})
        assert launch_res.status_code == 200
        launch_body = launch_res.json()
        assert launch_body["mission"]["selected_stage"] == "LAUNCH"
        assert launch_body["mission"]["stage_has_records"] is True

        mission_res = client.get("/api/v1/crew/ID-01/profile", params={"stage": "MISSION"})
        assert mission_res.status_code == 200
        mission_body = mission_res.json()
        assert mission_body["mission"]["selected_stage"] == "MISSION"
        assert mission_body["biometrics"][0]["value"] > launch_body["biometrics"][0]["value"]

        return_res = client.get("/api/v1/crew/ID-01/profile", params={"stage": "RETURN"})
        assert return_res.status_code == 200
        return_body = return_res.json()
        assert return_body["mission"]["selected_stage"] == "RETURN"
        assert return_body["mission"]["stage_has_records"] is False

        missing_res = client.get("/api/v1/crew/ID-99/profile")
        assert missing_res.status_code == 404


def test_crew_profile_reflects_captured_measurements_and_compliance(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    custom_ecg = [round(0.25 * ((idx % 10) - 5), 3) for idx in range(120)]

    with TestClient(app) as client:
        ingest_res = client.post(
            "/api/v1/measurements",
            json={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "source_type": "MANUAL",
                "items": [
                    {"metric_key": "resting_hr_bpm", "value_num": 64.0},
                    {"metric_key": "bp_systolic_mmhg", "value_num": 118.0},
                    {"metric_key": "bp_diastolic_mmhg", "value_num": 76.0},
                    {"metric_key": "hydration_ml", "value_num": 2800.0},
                    {"metric_key": "hemoglobin_g_dl", "value_num": 14.2},
                    {"metric_key": "urine_specific_gravity", "value_num": 1.012},
                    {
                        "metric_key": "work_shift_min",
                        "value_num": 340.0,
                        "payload_json": {"shift_mode": "IVA"},
                    },
                    {
                        "metric_key": "optic_sheath_right_mm",
                        "value_num": 5.9,
                        "payload_json": {"visual_acuity": "20/25"},
                    },
                    {
                        "metric_key": "ecg_lead_ii_mv",
                        "value_num": 1.15,
                        "payload_json": {"samples_mv": custom_ecg},
                    },
                ],
            },
        )
        assert ingest_res.status_code == 201

        res = client.get("/api/v1/crew/ID-01/profile")
        assert res.status_code == 200
        profile = res.json()

        bp_row = next(
            row for row in profile["daily_vitals"]["items"] if row["key"] == "blood_pressure"
        )
        assert bp_row["display_value"] == "118/76"
        assert profile["daily_vitals"]["on_target_count"] == 6

        assert profile["live_ecg"]["samples_mv"] == custom_ecg
        assert profile["biometric_scan"]["ocular_tone"] == "critical"
        assert profile["biometric_scan"]["scan_label"] == "CRITICAL"

        av_card = next(
            card for card in profile["clinical_labs"] if card["key"] == "auscultation_vision"
        )
        assert av_card["status_tone"] == "critical"
        assert "20/25" in av_card["display_value"]
        assert "5.9 mm" in av_card["detail"]

        iva_row = next(
            row for row in profile["environment_work"]["work_rows"] if row["key"] == "iva"
        )
        assert iva_row["display_value"] == "5h 40m"

        restricted_terms = [
            base64.b64decode("bmFzYQ==").decode("utf-8"),
            base64.b64decode("Y2hpbmE=").decode("utf-8"),
        ]
        restricted_pattern = re.compile(rf"\b({'|'.join(restricted_terms)})\b", re.IGNORECASE)
        serialized = json.dumps(profile)
        assert not restricted_pattern.search(serialized)
