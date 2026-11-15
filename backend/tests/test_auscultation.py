import base64
import hashlib
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.main import app
from db.seed import seed_database


def test_auscultation_sample_upload_stream_and_results(
    temp_db_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio_dir = tmp_path / "audio_store"
    monkeypatch.setenv("SPACESCAN_AUDIO_DIR", str(audio_dir))

    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    cardiac_bytes = b"\x1a\x45\xdf\xa3WEBM_ONBOARD_CARDIAC_MITRAL_30S_SAMPLE_DATA"
    cardiac_sha = hashlib.sha256(cardiac_bytes).hexdigest()

    pulmonary_bytes = b"\x1a\x45\xdf\xa3WEBM_ONBOARD_PULMONARY_UPPER_RIGHT_30S_DATA"
    pulmonary_sha = hashlib.sha256(pulmonary_bytes).hexdigest()

    with TestClient(app) as client:
        initial_res = client.get("/api/v1/auscultation/ID-01")
        assert initial_res.status_code == 200
        initial = initial_res.json()
        assert initial["crew_id"] == "ID-01"
        assert len(initial["phonocardiogram_samples"]) == 180
        assert len(initial["pulmonary_envelope_samples"]) == 180
        assert len(initial["clinical_bars"]) == 3
        assert len(initial["co2_trend"]) == 7
        assert len(initial["cardiac_sites"]) == 4
        assert len(initial["pulmonary_sites"]) == 4
        assert initial["cardiac_summary"]["saved_sites_count"] == 0
        assert initial["pulmonary_summary"]["saved_sites_count"] == 0

        create_cardiac = client.post(
            "/api/v1/auscultation/samples",
            data={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "organ_type": "CARDIAC",
                "anatomical_site": "mitral",
                "duration_sec": "30",
                "cabin_noise_dba": "47.8",
                "sha256_hex": cardiac_sha,
            },
            files={
                "audio_file": ("cardiac_mitral.webm", cardiac_bytes, "audio/webm"),
            },
        )
        assert create_cardiac.status_code == 201
        cardiac_created = create_cardiac.json()
        assert cardiac_created["sha256_hex"] == cardiac_sha
        assert cardiac_created["organ_type"] == "CARDIAC"
        assert cardiac_created["anatomical_site"] == "mitral"

        stream_res = client.get(
            f"/api/v1/auscultation/samples/{cardiac_created['sample_id']}/audio"
        )
        assert stream_res.status_code == 200
        assert stream_res.content == cardiac_bytes
        assert "audio/webm" in stream_res.headers["content-type"]

        create_pulmonary = client.post(
            "/api/v1/auscultation/samples",
            data={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "organ_type": "PULMONARY",
                "anatomical_site": "upper_right",
                "duration_sec": "30",
                "cabin_noise_dba": "48.4",
                "sha256_hex": pulmonary_sha,
            },
            files={
                "audio_file": (
                    "pulmonary_upper_right.webm",
                    pulmonary_bytes,
                    "audio/webm",
                ),
            },
        )
        assert create_pulmonary.status_code == 201

        updated_res = client.get("/api/v1/auscultation/ID-01")
        assert updated_res.status_code == 200
        updated = updated_res.json()
        assert updated["cardiac_summary"]["saved_sites_count"] == 1
        assert updated["pulmonary_summary"]["saved_sites_count"] == 1
        assert "Mitral: Saved (30s)" in updated["cardiac_progress_summary"]
        assert "Upper Right: Saved (30s)" in updated["pulmonary_progress_summary"]

        return_stage_res = client.get(
            "/api/v1/auscultation/ID-01",
            params={"stage": "RETURN"},
        )
        assert return_stage_res.status_code == 200
        assert return_stage_res.json()["stage_has_records"] is False

        missing_crew = client.get("/api/v1/auscultation/ID-99")
        assert missing_crew.status_code == 404

        missing_audio = client.get("/api/v1/auscultation/samples/9999/audio")
        assert missing_audio.status_code == 404


def test_auscultation_noise_gate_checksum_and_co2_correlation(
    temp_db_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio_dir = tmp_path / "audio_gate_store"
    monkeypatch.setenv("SPACESCAN_AUDIO_DIR", str(audio_dir))

    seed_database(
        db_path=temp_db_path,
        schema_path=SCHEMA_PATH,
        snapshot_path=SEED_SNAPSHOT_PATH,
    )

    sample_bytes = b"\x1a\x45\xdf\xa3WEBM_GATE_TEST_PAYLOAD"
    valid_sha = hashlib.sha256(sample_bytes).hexdigest()
    wrong_sha = "0" * 64

    with TestClient(app) as client:
        noisy_res = client.post(
            "/api/v1/auscultation/samples",
            data={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "organ_type": "CARDIAC",
                "anatomical_site": "aortic",
                "duration_sec": "30",
                "cabin_noise_dba": "56.2",
                "sha256_hex": valid_sha,
            },
            files={"audio_file": ("noisy.webm", sample_bytes, "audio/webm")},
        )
        assert noisy_res.status_code == 422

        bad_sha_res = client.post(
            "/api/v1/auscultation/samples",
            data={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "organ_type": "CARDIAC",
                "anatomical_site": "aortic",
                "duration_sec": "30",
                "cabin_noise_dba": "46.0",
                "sha256_hex": wrong_sha,
            },
            files={"audio_file": ("bad_sha.webm", sample_bytes, "audio/webm")},
        )
        assert bad_sha_res.status_code == 422

        wrong_site_res = client.post(
            "/api/v1/auscultation/samples",
            data={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "organ_type": "CARDIAC",
                "anatomical_site": "upper_left",
                "duration_sec": "30",
                "cabin_noise_dba": "46.0",
                "sha256_hex": valid_sha,
            },
            files={"audio_file": ("mismatch.webm", sample_bytes, "audio/webm")},
        )
        assert wrong_site_res.status_code == 422

        over_duration_res = client.post(
            "/api/v1/auscultation/samples",
            data={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "organ_type": "PULMONARY",
                "anatomical_site": "lower_left",
                "duration_sec": "45",
                "cabin_noise_dba": "46.0",
                "sha256_hex": valid_sha,
            },
            files={"audio_file": ("long.webm", sample_bytes, "audio/webm")},
        )
        assert over_duration_res.status_code == 422

        co2_ingest = client.post(
            "/api/v1/measurements",
            json={
                "crew_id": "ID-01",
                "mission_stage": "MISSION",
                "source_type": "AUTO",
                "items": [
                    {"metric_key": "cabin_co2_ppm", "value_num": 4200.0},
                ],
            },
        )
        assert co2_ingest.status_code == 201

        elevated_res = client.get("/api/v1/auscultation/ID-01")
        assert elevated_res.status_code == 200
        elevated = elevated_res.json()
        assert elevated["co2_current_mmhg"] == 4.2
        assert elevated["co2_tone"] == "critical"
        assert elevated["overall_tone"] == "critical"

        serialized = json.dumps(elevated)
        forbidden = [
            base64.b64decode(b"bmFzYQ==").decode("utf-8"),
            base64.b64decode(b"Y2hpbmE=").decode("utf-8"),
        ]
        pattern = re.compile(rf"\b({'|'.join(forbidden)})\b", re.IGNORECASE)
        assert pattern.search(serialized) is None
