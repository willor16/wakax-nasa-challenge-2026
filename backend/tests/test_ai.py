"""Tests for the onboard anomaly models, assistant guidance and physician review (D3-04/05)."""

import json
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import open_connection
from app.main import app as fastapi_app
from app.services import llm
from app.services.anomaly import META_PATH, PATTERN_INFO, detect, load_models
from app.services.diagnosis import (
    ReviewError,
    list_diagnoses,
    review_diagnosis,
    scan_crew_member,
)
from app.services.guide import search_articles
from db.seed import seed_database
from ml.simulate import FEATURES, PATTERNS, abnormal_days, build_dataset, correlation_matrix

PINS = {"ID-01": "1042", "ID-02": "2084", "ID-03": "3190"}


# ----------------------------------------------------------------- models ---

def test_simulation_is_reproducible_and_valid() -> None:
    assert np.linalg.eigvalsh(correlation_matrix()).min() > 0
    first, second = build_dataset(seed=3), build_dataset(seed=3)
    assert np.array_equal(first["train"], second["train"])
    assert first["train"].shape == (6000, len(FEATURES))


def test_exported_models_match_their_metadata() -> None:
    meta = json.loads(META_PATH.read_text())
    assert meta["features"] == list(FEATURES)
    assert meta["classes"] == ["healthy", *PATTERNS]
    assert meta["evaluation"]["healthy_flag_rate"] <= 0.05
    assert min(meta["evaluation"]["detection_rate"].values()) >= 0.8
    for name in (meta["classifier_file"], meta["autoencoder_file"]):
        size = (META_PATH.parent / name).stat().st_size
        assert 0 < size < 200_000  # small enough for onboard hardware


def test_models_recognize_simulated_patterns() -> None:
    models = load_models()
    rng = np.random.default_rng(99)
    for index, pattern in enumerate(PATTERNS, start=1):
        days = abnormal_days(pattern, 200, rng).astype(np.float32)
        probs = models.classifier.run(None, {"z": days})[1].reshape(len(days), -1)
        assert np.mean(probs.argmax(axis=1) == index) >= 0.8, pattern


@pytest.fixture()
def conn(temp_db_path: Path):
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with open_connection(temp_db_path) as connection:
        yield connection


def test_detect_on_seeded_crew(conn) -> None:
    eyes = detect(conn, "ID-01")  # seed: right eye pressure and sheath well above baseline
    assert eyes.is_anomaly and eyes.pattern == "ocular"
    assert eyes.top_metrics[0]["metric_key"] in {"iop_right_mmhg", "optic_sheath_right_mm"}
    assert eyes.anomaly_score >= 1
    calm = detect(conn, "ID-03")  # seed: readings close to baseline
    assert not calm.is_anomaly and calm.pattern is None


# -------------------------------------------------------------- assistant ---

def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _answer(payload: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["format"] == "json" and body["stream"] is False
        return httpx.Response(200, json={"response": json.dumps(payload)})
    return handler


FINDING = {
    "pattern_label_en": "Eye pressure and optic nerve changes",
    "top_metrics": [{"display_name_en": "Right Intraocular Pressure", "value": 17.5,
                     "unit": "mmHg", "baseline": 14.5, "z": 5.2}],
    "article_id": "wiki-vision-01",
}
ARTICLES = [{"id": "wiki-vision-01", "title_en": "Eye Protocol", "escalation_en": "Call now.",
             "steps": [{"title_en": "Repeat the Eye Scan", "detail_en": ""}]}]
GOOD = {
    "summary": "Both eye readings rose above the usual range.",
    "steps": [{"title": f"Step {i}", "detail": "Do this calmly."} for i in range(1, 5)],
    "cited_article_ids": ["wiki-vision-01", "wiki-unknown"],
}


def test_valid_answer_is_used_and_trimmed() -> None:
    guidance = llm.generate_guidance(FINDING, ARTICLES, "vision", client=_client(_answer(GOOD)))
    assert guidance.source == "assistant"
    assert len(guidance.steps) == 3
    assert guidance.cited_article_ids == ["wiki-vision-01"]  # unknown ids dropped


@pytest.mark.parametrize("bad", [
    {**GOOD, "steps": GOOD["steps"][:2]},                          # too few steps
    {**GOOD, "summary": "Our neural model flagged this."},         # internal tech word
    {**GOOD, "cited_article_ids": ["wiki-other"]},                  # nothing valid cited
    {**GOOD, "summary": "Lecturas fuera de rango según el médico."},  # not English
])
def test_invalid_answers_fall_back(bad: dict) -> None:
    guidance = llm.generate_guidance(FINDING, ARTICLES, "vision", client=_client(_answer(bad)))
    assert guidance.source == "fallback" and guidance.issues
    assert guidance.cited_article_ids == ["wiki-vision-01"]
    assert len(guidance.steps) == 3


def test_unreachable_assistant_falls_back() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")
    guidance = llm.generate_guidance(FINDING, ARTICLES, "vision", client=_client(down))
    assert guidance.source == "fallback"
    assert guidance.issues[0].startswith("assistant unavailable")
    assert "Eye pressure and optic nerve changes" in guidance.summary_en


def test_pattern_info_points_to_existing_guide(conn) -> None:
    ids = {r["id"] for r in search_articles(conn)}
    assert {info["article"] for info in PATTERN_INFO.values()} <= ids


# ------------------------------------------------------- physician review ---

def test_scan_review_and_promotion_flow(conn) -> None:
    client = _client(_answer(GOOD))
    first = scan_crew_member(conn, "ID-01", client=client)
    diagnosis = first["diagnosis"]
    assert diagnosis["validation_status"] == "PENDING_REVIEW"
    assert diagnosis["guidance_source"] == "assistant"
    assert scan_crew_member(conn, "ID-01", client=client)["repeated"] is True
    assert scan_crew_member(conn, "ID-03", client=client)["diagnosis"] is None

    # The crew member sees nothing until the physician reviews it.
    assert list_diagnoses(conn, viewer_id="ID-01", viewer_role="PILOT") == []
    pending = list_diagnoses(conn, viewer_id="ID-03", viewer_role="PHYSICIAN",
                             status="PENDING_REVIEW")
    assert [d["id"] for d in pending] == [diagnosis["id"]]

    result = review_diagnosis(conn, diagnosis["id"], "ID-03", "PROMOTED_TO_GUIDE",
                              "Repeat the eye scan tomorrow morning.")
    assert result["validation_status"] == "PROMOTED_TO_GUIDE"
    alert = conn.execute("SELECT * FROM alerts WHERE id = ?", (result["alert_id"],)).fetchone()
    assert alert["crew_id"] == "ID-01" and alert["severity"] == "INFO"
    assert alert["message_en"].endswith("Physician note: Repeat the eye scan tomorrow morning.")
    case = search_articles(conn, "validated case")
    assert case[0]["id"] == result["guide_article_id"]
    assert case[0]["escalation_en"] == "Repeat the eye scan tomorrow morning."
    assert list_diagnoses(conn, viewer_id="ID-01", viewer_role="PILOT")[0]["id"] == diagnosis["id"]

    with pytest.raises(ReviewError):
        review_diagnosis(conn, diagnosis["id"], "ID-03", "REJECTED")


def test_reject_sends_nothing_to_the_crew(conn) -> None:
    diagnosis = scan_crew_member(conn, "ID-01", client=_client(_answer(GOOD)))["diagnosis"]
    before = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    result = review_diagnosis(conn, diagnosis["id"], "ID-03", "REJECTED", "Sensor error.")
    assert result["alert_id"] is None and result["guide_article_id"] is None
    assert conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == before


def _headers(client: TestClient, crew_id: str) -> dict[str, str]:
    login = client.post("/api/v1/auth/login", json={"crew_id": crew_id, "pin": PINS[crew_id]})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_api_permissions(temp_db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "LLM_URL", "http://127.0.0.1:9")  # no assistant: fallback
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with TestClient(fastapi_app) as client:
        pilot, operator, doctor = (_headers(client, c) for c in ("ID-01", "ID-02", "ID-03"))
        scan = client.post("/api/v1/diagnosis/anomalies", json={}, headers=pilot)
        assert scan.status_code == 200
        diagnosis = scan.json()["diagnosis"]
        assert diagnosis["guidance_source"] == "fallback"

        assert client.post("/api/v1/diagnosis/anomalies", json={"crew_id": "ID-01"},
                           headers=operator).status_code == 403
        assert client.post("/api/v1/diagnosis/anomalies", json={"crew_id": "ID-09"},
                           headers=doctor).status_code == 404

        url = f"/api/v1/diagnosis/{diagnosis['id']}/review"
        assert client.post(url, json={"decision": "APPROVED"}, headers=pilot).status_code == 403
        assert client.get("/api/v1/diagnosis", headers=doctor).json()["pending"] == 1
        assert client.post(url, json={"decision": "APPROVED"}, headers=doctor).status_code == 200
        assert client.post(url, json={"decision": "APPROVED"}, headers=doctor).status_code == 409
        assert client.post("/api/v1/diagnosis/999/review", json={"decision": "APPROVED"},
                           headers=doctor).status_code == 404
        mine = client.get("/api/v1/diagnosis", headers=pilot).json()["items"]
        assert [d["validation_status"] for d in mine] == ["APPROVED"]
