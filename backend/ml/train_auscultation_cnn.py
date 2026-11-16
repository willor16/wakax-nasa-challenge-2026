"""Train the onboard heart and lung sound classifiers and export them for CPU inference (M5).

Run before flight (needs the ``train`` extra for ``onnx``):

    uv run python -m ml.train_auscultation_cnn

For each organ a small 1-D convolutional network (``ml.cnn_numpy``) learns the log-mel
windows of simulated sounds (``ml.simulate_auscultation``), is checked on held-out
recordings, exported to ONNX and verified against onnxruntime. Outputs, kept in the
repository so the cabin computer needs no network:

* ``models/auscultation_cnn_cardiac.onnx`` and ``models/auscultation_cnn_pulmonary.onnx``
* ``models/auscultation_cnn_meta.json`` (classes, feature settings, accuracy, version)

The training sounds are simulated, so this is a demonstration model: its classes are
reported as "suspected" and every non-normal result goes to the crew physician.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort

from app.services.acoustics import (
    FEATURE_BANDS,
    FEATURE_CHANNELS,
    FEATURE_CONFIG,
    FEATURE_FRAMES,
    FFT_SIZE,
    feature_windows,
)
from ml.cnn_numpy import Conv1DNet
from ml.simulate_auscultation import CARDIAC_CLASSES, PULMONARY_CLASSES, SAMPLE_RATE, generate

MODELS = Path(__file__).resolve().parents[1] / "models"
CLASSES = {"CARDIAC": CARDIAC_CLASSES, "PULMONARY": PULMONARY_CLASSES}
# Recordings per class; each 30 s recording gives several windows. Lung windows are
# longer (fewer per recording), so the lungs get more recordings.
TRAIN_RECORDINGS = {"CARDIAC": 70, "PULMONARY": 160}
TEST_RECORDINGS = 20
SECONDS = 30.0


def dataset(organ: str, recordings: int, seed: int) -> tuple[np.ndarray, np.ndarray, list]:
    xs, ys, groups = [], [], []
    for label, kind in enumerate(CLASSES[organ]):
        for r in range(recordings):
            sound = generate(organ, kind, SECONDS, seed + label * 10_000 + r)
            windows = feature_windows(sound, SAMPLE_RATE, organ)
            xs.append(windows)
            ys.append(np.full(len(windows), label))
            groups.append((label, len(windows)))
    return np.concatenate(xs), np.concatenate(ys), groups


def recording_accuracy(net: Conv1DNet, x: np.ndarray, groups: list) -> dict[str, float]:
    """Per-class accuracy of whole recordings (window probabilities averaged), as in the app."""
    probs = net.predict(x)
    hits: dict[int, list[bool]] = {}
    start = 0
    for label, count in groups:
        guess = int(probs[start : start + count].mean(axis=0).argmax())
        hits.setdefault(label, []).append(guess == label)
        start += count
    return {str(label): round(float(np.mean(v)), 3) for label, v in hits.items()}


def train_organ(organ: str) -> dict:
    print(f"{organ}: building simulated recordings")
    x_train, y_train, _ = dataset(organ, TRAIN_RECORDINGS[organ], seed=1)
    x_test, _y_test, test_groups = dataset(organ, TEST_RECORDINGS, seed=900_000)
    net = Conv1DNet(in_channels=FEATURE_CHANNELS, classes=len(CLASSES[organ]), seed=7)
    print(f"{organ}: training on {len(x_train)} windows")
    net.fit(x_train, y_train, epochs=24)
    per_class = recording_accuracy(net, x_test, test_groups)
    accuracy = {CLASSES[organ][int(k)]: v for k, v in per_class.items()}
    overall = round(float(np.mean(list(accuracy.values()))), 3)
    print(f"{organ}: held-out recording accuracy {overall} {accuracy}")

    path = MODELS / f"auscultation_cnn_{organ.lower()}.onnx"
    model = net.to_onnx(FEATURE_FRAMES)
    onnx.checker.check_model(model)
    onnx.save(model, path)
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    check = x_test[:32].astype(np.float32)
    diff = np.abs(session.run(None, {"features": check})[0] - net.predict(check)).max()
    assert diff < 1e-4, f"exported model differs from numpy by {diff}"
    print(
        f"{organ}: exported {path.name} ({path.stat().st_size / 1024:.1f} KB), max diff {diff:.2e}"
    )
    return {
        "file": path.name,
        "classes": list(CLASSES[organ]),
        "accuracy": accuracy,
        "accuracy_overall": overall,
        "window_s": FEATURE_CONFIG[organ]["window_s"],
        "fmin_hz": FEATURE_CONFIG[organ]["fmin"],
        "fmax_hz": FEATURE_CONFIG[organ]["fmax"],
    }


def main() -> None:
    MODELS.mkdir(exist_ok=True)
    organs = {organ: train_organ(organ) for organ in ("CARDIAC", "PULMONARY")}
    meta = {
        "version": datetime.now(UTC).strftime("%Y%m%d"),
        "trained_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "training_data": "simulated heart and lung sounds (ml/simulate_auscultation.py)",
        "note": "Demonstration model: results are suspicions for the crew physician to review.",
        "sample_rate_hz": SAMPLE_RATE,
        "features": {
            "bands": FEATURE_BANDS,
            "channels": FEATURE_CHANNELS,
            "frames": FEATURE_FRAMES,
            "fft": FFT_SIZE,
        },
        "organs": organs,
    }
    (MODELS / "auscultation_cnn_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    total = sum((MODELS / o["file"]).stat().st_size for o in organs.values())
    print(f"saved auscultation_cnn_meta.json; models total {total / 1024:.1f} KB")


if __name__ == "__main__":
    main()
