import base64
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import BACKEND_DIR, SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import open_connection
from app.main import app
from db.seed import seed_database


def test_list_metric_catalog_and_regulatory_compliance(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    with TestClient(app) as client:
        res = client.get("/api/v1/metrics/catalog")
        assert res.status_code == 200
        metrics = res.json()
        assert len(metrics) == 28

        keys = {item["metric_key"] for item in metrics}
        expected_dev2_keys = {
            "bp_diastolic_mmhg",
            "ecg_lead_ii_mv",
            "orthostatic_hr_delta_bpm",
            "bmi_kg_m2",
            "hemoglobin_g_dl",
            "urine_specific_gravity",
            "urine_protein_mg_dl",
            "respiratory_rate_brpm",
            "cardiorespiratory_index",
            "work_shift_min",
        }
        assert expected_dev2_keys.issubset(keys)

        restricted_terms = [
            base64.b64decode("bmFzYQ==").decode("utf-8"),
            base64.b64decode("Y2hpbmE=").decode("utf-8"),
        ]
        restricted_pattern = re.compile(rf"\b({'|'.join(restricted_terms)})\b", re.IGNORECASE)
        for item in metrics:
            assert not restricted_pattern.search(item["display_name_en"])
            assert not restricted_pattern.search(item["clinical_reference"])

        vision_res = client.get("/api/v1/metrics/catalog", params={"category": "VISION"})
        assert vision_res.status_code == 200
        vision_metrics = vision_res.json()
        assert len(vision_metrics) == 4
        assert all(m["category"] == "VISION" for m in vision_metrics)


def test_ingest_alerts_quiet_hours_and_atomic_rollback(temp_db_path: Path) -> None:
    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    with TestClient(app) as client:
        quiet_warn_res = client.post(
            "/api/v1/measurements",
            json={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "source_type": "MANUAL",
                "recorded_at_utc": "2026-11-15T23:15:00Z",
                "items": [
                    {"metric_key": "bp_diastolic_mmhg", "value_num": 76.0},
                    {"metric_key": "optic_sheath_right_mm", "value_num": 5.4},
                ],
            },
        )
        assert quiet_warn_res.status_code == 201
        warn_body = quiet_warn_res.json()
        assert len(warn_body["inserted_ids"]) == 2
        assert len(warn_body["alerts_created"]) == 1
        assert warn_body["streak"]["logs_completed"] == 1

        quiet_crit_res = client.post(
            "/api/v1/measurements",
            json={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "source_type": "AUTO",
                "recorded_at_utc": "2026-11-15T23:45:00Z",
                "items": [
                    {
                        "metric_key": "spo2_pct",
                        "value_num": 88.0,
                        "payload_json": {"sensor": "pulse-oximeter"},
                    }
                ],
            },
        )
        assert quiet_crit_res.status_code == 201
        crit_body = quiet_crit_res.json()
        assert len(crit_body["alerts_created"]) == 1
        assert crit_body["streak"]["logs_completed"] == 2

        before_rows = client.get("/api/v1/measurements", params={"crew_id": "ID-02"}).json()
        invalid_batch = client.post(
            "/api/v1/measurements",
            json={
                "crew_id": "ID-02",
                "mission_stage": "MISSION",
                "items": [
                    {"metric_key": "resting_hr_bpm", "value_num": 61.0},
                    {"metric_key": "non_existent_metric_xyz", "value_num": 10.0},
                ],
            },
        )
        assert invalid_batch.status_code == 422
        after_rows = client.get("/api/v1/measurements", params={"crew_id": "ID-02"}).json()
        assert len(after_rows) == len(before_rows)

    conn = open_connection(temp_db_path)
    try:
        warn_alert = conn.execute(
            "SELECT severity, is_quiet_deferred FROM alerts WHERE id = ?",
            (warn_body["alerts_created"][0],),
        ).fetchone()
        assert warn_alert["severity"] == "WARNING"
        assert warn_alert["is_quiet_deferred"] == 1

        crit_alert = conn.execute(
            "SELECT severity, is_quiet_deferred FROM alerts WHERE id = ?",
            (crit_body["alerts_created"][0],),
        ).fetchone()
        assert crit_alert["severity"] == "CRITICAL"
        assert crit_alert["is_quiet_deferred"] == 0
    finally:
        conn.close()


def test_validation_and_query_filtering(temp_db_path: Path) -> None:
    prod_db_file = BACKEND_DIR / "db" / "spacescan.db"
    prod_existed_before = prod_db_file.exists()

    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    with TestClient(app) as client:
        missing_crew = client.post(
            "/api/v1/measurements",
            json={
                "crew_id": "ID-99",
                "mission_stage": "MISSION",
                "items": [{"metric_key": "resting_hr_bpm", "value_num": 64.0}],
            },
        )
        assert missing_crew.status_code == 404

        bad_query_ts = client.get(
            "/api/v1/measurements",
            params={"crew_id": "ID-01", "from_utc": "not-a-timestamp"},
        )
        assert bad_query_ts.status_code == 422

        filtered = client.get(
            "/api/v1/measurements",
            params={
                "crew_id": "ID-01",
                "category": "VISION",
                "mission_stage": "MISSION",
                "limit": 10,
            },
        )
        assert filtered.status_code == 200
        rows = filtered.json()
        assert len(rows) == 4
        assert all(row["crew_id"] == "ID-01" for row in rows)

    if not prod_existed_before:
        assert not prod_db_file.exists()
