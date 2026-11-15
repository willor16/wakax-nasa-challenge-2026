import base64
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth_utils import create_access_token
from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.main import app
from db.seed import seed_database


def test_vision_exam_bilateral_summary_and_capture_roundtrip(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    with TestClient(app) as client:
        base_res = client.get("/api/v1/vision/ID-01")
        assert base_res.status_code == 200
        exam = base_res.json()
        assert exam["crew_id"] == "ID-01"
        assert exam["left_eye"]["side"] == "LEFT"
        assert exam["right_eye"]["side"] == "RIGHT"
        assert len(exam["ocular_metrics"]) == 3
        assert len(exam["preventive_steps"]) == 3
        assert len(exam["trend_points"]) >= 4
        assert exam["trend_points"][-1]["is_projected"] is True

        launch_res = client.get("/api/v1/vision/ID-01", params={"stage": "LAUNCH"})
        assert launch_res.status_code == 200
        assert launch_res.json()["stage_has_records"] is True

        return_res = client.get("/api/v1/vision/ID-01", params={"stage": "RETURN"})
        assert return_res.status_code == 200
        assert return_res.json()["stage_has_records"] is False

        ingest_res = client.post(
            "/api/v1/measurements",
            json={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "source_type": "MANUAL",
                "items": [
                    {
                        "metric_key": "optic_sheath_left_mm",
                        "value_num": 5.5,
                        "payload_json": {
                            "retinal_thickness_um": 104,
                            "visual_acuity": "20/20",
                        },
                    },
                    {
                        "metric_key": "optic_sheath_right_mm",
                        "value_num": 5.9,
                        "payload_json": {
                            "retinal_thickness_um": 104,
                            "visual_acuity": "20/20",
                        },
                    },
                    {"metric_key": "iop_left_mmhg", "value_num": 15.8},
                    {"metric_key": "iop_right_mmhg", "value_num": 16.2},
                ],
            },
        )
        assert ingest_res.status_code == 201

        elevated_res = client.get("/api/v1/vision/ID-01")
        assert elevated_res.status_code == 200
        elevated = elevated_res.json()
        assert elevated["overall_tone"] == "critical"
        assert elevated["header_status_badge"] == "RIGHT EYE ELEVATED"
        assert elevated["right_eye"]["sheath_mm"] == 5.9
        assert elevated["left_eye"]["sheath_mm"] == 5.5
        assert elevated["ocular_metrics"][1]["display_value"] == "104"
        assert elevated["ocular_metrics"][2]["display_value"] == "20/20"

        missing_res = client.get("/api/v1/vision/ID-99")
        assert missing_res.status_code == 404


def test_vision_physician_review_rbac_and_compliance(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    pilot_token = create_access_token(
        {
            "id": "ID-01",
            "code": "ID·01",
            "full_name": "Elena Vargas",
            "short_name": "E. VARGAS",
            "role": "PILOT",
        }
    )
    physician_token = create_access_token(
        {
            "id": "ID-03",
            "code": "ID·03",
            "full_name": "Amara Okafor",
            "short_name": "A. OKAFOR",
            "role": "PHYSICIAN",
        }
    )

    with TestClient(app) as client:
        denied_res = client.post(
            "/api/v1/vision/ID-01/review",
            headers={"Authorization": f"Bearer {pilot_token}"},
            json={
                "validation_status": "APPROVED",
                "physician_notes_en": "Attempted review without physician role.",
            },
        )
        assert denied_res.status_code == 403

        review_res = client.post(
            "/api/v1/vision/ID-01/review",
            headers={"Authorization": f"Bearer {physician_token}"},
            json={
                "validation_status": "APPROVED",
                "physician_notes_en": "Evening lower-body pressure session cleared for Day 048.",
                "preventive_steps": [
                    {
                        "step_number": 1,
                        "code_label": "01 · EVENING PRESSURE SESSION",
                        "title": "Lower-Body Negative Pressure",
                        "description": "30-minute session at -25 mmHg before sleep.",
                        "accent_tone": "ok",
                    },
                    {
                        "step_number": 2,
                        "code_label": "02 · CABIN AIRFLOW",
                        "title": "Sleep Station Ventilation",
                        "description": "Keep sleep airflow at 85% with local CO₂ below 3.0 mmHg.",
                        "accent_tone": "ok",
                    },
                    {
                        "step_number": 3,
                        "code_label": "03 · FOLLOW-UP CHECK",
                        "title": "Scheduled Ultrasound",
                        "description": "Repeat bilateral measurement on Day 050.",
                        "accent_tone": "ice",
                    },
                ],
            },
        )
        assert review_res.status_code == 201
        created = review_res.json()
        assert created["validation_status"] == "APPROVED"
        assert created["validated_by"] == "ID-03"
        assert created["reviewer_label"] == "Reviewed by Dr. A. Okafor"

        updated_exam = client.get("/api/v1/vision/ID-01").json()
        assert updated_exam["reviewed_by_label"] == "Reviewed by Dr. A. Okafor"
        assert "Evening lower-body pressure" in (updated_exam["physician_notes_en"] or "")

        restricted_terms = [
            base64.b64decode("bmFzYQ==").decode("utf-8"),
            base64.b64decode("Y2hpbmE=").decode("utf-8"),
        ]
        restricted_pattern = re.compile(rf"\b({'|'.join(restricted_terms)})\b", re.IGNORECASE)
        assert not restricted_pattern.search(json.dumps(updated_exam))
