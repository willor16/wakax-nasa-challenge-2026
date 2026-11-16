"""Heart and lung sound classification, compressed uploads and physician review (M5)."""

import gzip
import hashlib
import json
import time

import numpy as np
import pytest

from app.services import acoustic_review, acoustics, llm
from ml.cnn_numpy import Conv1DNet
from ml.simulate_auscultation import CARDIAC_CLASSES, PULMONARY_CLASSES, generate

RATE = 4000


@pytest.fixture(autouse=True)
def no_language_server(monkeypatch):
    """Tests never wait for the local assistant: a closed port makes it fall back at once."""
    monkeypatch.setattr(llm, "LLM_URL", "http://127.0.0.1:9")


def _wav(signal) -> tuple[bytes, str]:
    data = acoustics.write_wav(signal, RATE)
    return data, hashlib.sha256(data).hexdigest()


def _upload(
    client, headers, data, digest, organ="PULMONARY", site="lower_left", encoding="identity"
):
    return client.post(
        "/api/v1/auscultation/samples",
        headers=headers,
        data={
            "organ_type": organ,
            "anatomical_site": site,
            "cabin_noise_dba": "48",
            "sha256_hex": digest,
            "content_encoding": encoding,
        },
        files={"audio_file": ("sample.wav", data, "audio/wav")},
    )


def test_features_have_the_expected_shape():
    sound = generate("PULMONARY", "normal_vesicular", 30, seed=3)
    windows = acoustics.feature_windows(sound, RATE, "PULMONARY")
    assert windows.shape[1:] == (acoustics.FEATURE_CHANNELS, acoustics.FEATURE_FRAMES)
    assert windows.dtype == np.float32
    assert len(acoustics.feature_windows(sound, RATE, "CARDIAC")) > len(windows)


def test_models_are_small_and_match_the_numpy_network():
    meta = json.loads(acoustics.CLASSIFIER_META.read_text())
    total = sum((acoustics.MODELS_DIR / o["file"]).stat().st_size for o in meta["organs"].values())
    assert total < 2 * 1024 * 1024
    assert meta["organs"]["CARDIAC"]["classes"] == list(CARDIAC_CLASSES)
    assert meta["organs"]["PULMONARY"]["classes"] == list(PULMONARY_CLASSES)
    assert "simulated" in meta["training_data"]
    # The exported graph computes exactly what the numpy network computes.
    net = Conv1DNet(in_channels=acoustics.FEATURE_CHANNELS, classes=5, seed=3)
    import onnxruntime as ort

    session = ort.InferenceSession(
        net.to_onnx(acoustics.FEATURE_FRAMES).SerializeToString(),
        providers=["CPUExecutionProvider"],
    )
    x = (
        np.random.default_rng(0)
        .normal(size=(4, acoustics.FEATURE_CHANNELS, acoustics.FEATURE_FRAMES))
        .astype(np.float32)
    )
    assert np.abs(session.run(None, {"features": x})[0] - net.predict(x)).max() < 1e-4


@pytest.mark.parametrize(
    ("organ", "kind"),
    [
        ("CARDIAC", "normal_s1_s2"),
        ("CARDIAC", "systolic_murmur_suspected"),
        ("CARDIAC", "irregular_rhythm"),
        ("PULMONARY", "normal_vesicular"),
        ("PULMONARY", "wheeze_suspected"),
        ("PULMONARY", "crackle_suspected"),
    ],
)
def test_recordings_are_classified_quickly(organ, kind):
    sound = generate(organ, kind, 30, seed=424_242)
    started = time.perf_counter()
    result = acoustics.classify(sound, RATE, organ)
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert result["class_key"] == kind
    assert result["confidence_pct"] >= 60
    assert result["needs_review"] == (kind in acoustics.REVIEW_CLASSES)
    assert elapsed_ms < 300 and result["inference_ms"] < 300


def test_gzip_upload_is_verified_and_recorded(client, login):
    data, digest = _wav(acoustics.simulate_lungs(15, 30, RATE, seed=8))
    packed = gzip.compress(data, compresslevel=9)
    saved = _upload(client, login("ID-02"), packed, digest, site="upper_left", encoding="gzip")
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["sha256_verified"] is True
    assert body["payload_kb"] == pytest.approx(len(packed) / 1024, abs=0.1)
    assert body["wav_kb"] <= 250
    assert body["compression_ratio"] >= 1.0
    assert body["classification"]["class_key"] == "normal_vesicular"
    assert body["finding_id"] is None
    # The stored file is the original WAV, playable and identical to what was captured.
    audio = client.get(f"/api/v1/auscultation/samples/{body['id']}/audio", headers=login("ID-02"))
    assert hashlib.sha256(audio.content).hexdigest() == digest


def test_damaged_or_inflating_gzip_is_rejected(client, login):
    data, digest = _wav(acoustics.simulate_lungs(15, 30, RATE, seed=9))
    broken = _upload(client, login("ID-02"), b"\x1f\x8b not gzip", digest, encoding="gzip")
    assert broken.status_code == 422
    bomb = gzip.compress(b"\0" * (7 * 1024 * 1024))
    inflated = _upload(
        client, login("ID-02"), bomb, hashlib.sha256(b"x").hexdigest(), encoding="gzip"
    )
    assert inflated.status_code == 422


def test_wheeze_opens_a_finding_for_the_physician(client, login):
    me = login("ID-01")
    data, digest = _wav(generate("PULMONARY", "wheeze_suspected", 30, seed=77))
    saved = _upload(client, me, data, digest)
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["classification"]["class_key"] == "wheeze_suspected"
    assert body["finding_id"] and body["alerts_created"]

    pending = client.get(
        "/api/v1/diagnosis", headers=login("ID-03"), params={"status": "PENDING_REVIEW"}
    ).json()["items"]
    finding = next(f for f in pending if f["id"] == body["finding_id"])
    assert finding["pattern_key"] == "auscultation_wheeze_suspected"
    assert len(finding["preventive_steps"]) == 3
    assert "wheeze" in finding["llm_summary_en"].lower()
    assert finding["guidance_source"] == "fallback"  # assistant unreachable in tests

    results = client.get("/api/v1/auscultation/ID-01", headers=me).json()["pulmonary"]
    assert results["classification"]["class_key"] == "wheeze_suspected"
    assert results["interpretation"]["status"] == "PENDING_REVIEW"
    assert results["interpretation"]["finding_id"] == body["finding_id"]
    assert results["audio_url"].endswith(f"/samples/{body['id']}/audio")
    assert results["needs_physician_review"] is True

    again = _upload(
        client,
        me,
        *_wav(generate("PULMONARY", "wheeze_suspected", 30, seed=78)),
        site="upper_right",
    ).json()
    assert again["finding_id"] == body["finding_id"] and again["finding_repeated"] is True


def test_assistant_rewrites_the_interpretation_when_available(client, login, monkeypatch):
    me = login("ID-04")
    data, digest = _wav(generate("CARDIAC", "systolic_murmur_suspected", 30, seed=55))
    finding_id = _upload(client, me, data, digest, organ="CARDIAC", site="aortic").json()[
        "finding_id"
    ]
    assert finding_id

    answer = {
        "summary": "A soft sound between the heartbeats was heard at the aortic spot.",
        "steps": [
            {"title": "Rest seated", "detail": "Sit quietly for 10 minutes."},
            {"title": "Drink water", "detail": "Drink 400 mL of water."},
            {"title": "Pause hard exercise", "detail": "Swap heavy work for rest."},
        ],
        "cited_article_ids": ["wiki-cardio-01"],
    }

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": json.dumps(answer)}

    class FakeClient:
        def post(self, *_args, **_kwargs):
            return FakeResponse()

    assert acoustic_review.refine_finding(finding_id, client=FakeClient()) == "assistant"
    pending = client.get(
        "/api/v1/diagnosis", headers=login("ID-03"), params={"status": "PENDING_REVIEW"}
    ).json()["items"]
    finding = next(f for f in pending if f["id"] == finding_id)
    assert finding["guidance_source"] == "assistant"
    assert finding["llm_summary_en"].startswith("A soft sound")


def test_normal_recording_opens_nothing(client, login):
    data, digest = _wav(generate("CARDIAC", "normal_s1_s2", 30, seed=12))
    body = _upload(client, login("ID-02"), data, digest, organ="CARDIAC", site="mitral").json()
    assert body["classification"]["class_key"] == "normal_s1_s2"
    assert body["finding_id"] is None
