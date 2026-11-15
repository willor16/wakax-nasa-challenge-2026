"""Train the onboard anomaly models and export them for CPU inference (D3-04).

Run before flight (needs the ``train`` extra):

    uv run python -m ml.train_anomaly

Two small neural networks work together:

* ``pattern_classifier``: learns healthy days and the known abnormal patterns
  (ocular, dehydration, fatigue, low oxygen, decoupled heart rhythm) and names
  the closest one. A day is flagged when the chance of "healthy" drops below a
  cut tuned on held-out healthy days to flag about 2 in 100.
* ``novelty_autoencoder``: learns to rebuild healthy days only. A day it cannot
  rebuild (error above the 99.5th percentile of healthy days) is unusual even if
  it matches no known pattern.

An autoencoder alone misses large but coherent shifts (both eyes rising
together still "looks" like healthy physiology to it), which is why the pattern
network leads and the autoencoder covers the unknown.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import onnxruntime as ort
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
from sklearn.neural_network import MLPClassifier, MLPRegressor

from ml.simulate import FEATURES, PATTERNS, abnormal_days, build_dataset, healthy_days

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
CLASSIFIER_FILE = "pattern_classifier.onnx"
AUTOENCODER_FILE = "novelty_autoencoder.onnx"
META_FILE = "anomaly_models.json"
MODEL_VERSION = "1.0.0"
CLASSES = ("healthy", *PATTERNS)
TARGET_HEALTHY_FLAG_RATE = 0.02
NOVELTY_PERCENTILE = 99.5
TRAIN_PER_PATTERN = 1200
SEED = 7


def reconstruction_error(original: np.ndarray, rebuilt: np.ndarray) -> np.ndarray:
    return np.mean((original - rebuilt) ** 2, axis=1)


def unseen_pattern(n: int, rng: np.random.Generator) -> np.ndarray:
    """A pattern never shown in training (high glucose with fever) to test novelty."""
    days = healthy_days(n, rng)
    days[:, FEATURES.index("blood_glucose_mg_dl")] += rng.uniform(3.0, 4.5, n)
    days[:, FEATURES.index("body_temp_c")] += rng.uniform(1.5, 2.5, n)
    return days.astype(np.float32)


def train(seed: int = SEED) -> tuple[MLPClassifier, MLPRegressor, dict]:
    data = build_dataset(seed=seed)
    rng = np.random.default_rng(seed + 100)

    features = [data["train"]]
    labels = [np.zeros(len(data["train"]), dtype=np.int64)]
    for index, pattern in enumerate(PATTERNS, start=1):
        days = abnormal_days(pattern, TRAIN_PER_PATTERN, rng).astype(np.float32)
        features.append(days)
        labels.append(np.full(len(days), index, dtype=np.int64))
    classifier = MLPClassifier(hidden_layer_sizes=(32, 16), activation="relu", alpha=1e-3,
                               max_iter=400, random_state=seed)
    classifier.fit(np.vstack(features), np.concatenate(labels))

    autoencoder = MLPRegressor(hidden_layer_sizes=(8, 3, 8), activation="tanh", alpha=1e-4,
                               max_iter=600, random_state=seed)
    autoencoder.fit(data["train"], data["train"])

    p_healthy_val = classifier.predict_proba(data["val"])[:, 0]
    healthy_cut = float(np.quantile(p_healthy_val, TARGET_HEALTHY_FLAG_RATE))
    novelty_threshold = float(np.percentile(
        reconstruction_error(data["val"], autoencoder.predict(data["val"])), NOVELTY_PERCENTILE
    ))

    def flagged(days: np.ndarray) -> np.ndarray:
        by_pattern = classifier.predict_proba(days)[:, 0] < healthy_cut
        by_novelty = reconstruction_error(days, autoencoder.predict(days)) >= novelty_threshold
        return by_pattern | by_novelty

    report = {
        "healthy_cut": healthy_cut,
        "novelty_threshold": novelty_threshold,
        "healthy_flag_rate": float(np.mean(flagged(data["test"]))),
        "detection_rate": {
            p: float(np.mean(flagged(data[f"abnormal_{p}"]))) for p in PATTERNS
        },
        "named_correctly": {
            p: float(np.mean(classifier.predict(data[f"abnormal_{p}"]) == i))
            for i, p in enumerate(PATTERNS, start=1)
        },
        "unseen_pattern_detection": float(np.mean(flagged(unseen_pattern(300, rng)))),
    }
    return classifier, autoencoder, report


def _check_export(path: Path, expected: np.ndarray, probe: np.ndarray, output: int) -> None:
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    result = session.run(None, {"z": probe})[output].reshape(len(probe), -1)
    assert np.allclose(result, expected, atol=1e-4), f"export mismatch in {path.name}"


def export(classifier: MLPClassifier, autoencoder: MLPRegressor, report: dict,
           out_dir: Path = MODELS_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    input_type = [("z", FloatTensorType([None, len(FEATURES)]))]
    probe = build_dataset(seed=SEED + 1)["test"][:200]

    clf_onnx = convert_sklearn(classifier, initial_types=input_type, target_opset=17,
                               options={id(classifier): {"zipmap": False}})
    (out_dir / CLASSIFIER_FILE).write_bytes(clf_onnx.SerializeToString())
    _check_export(out_dir / CLASSIFIER_FILE, classifier.predict_proba(probe), probe, output=1)

    ae_onnx = convert_sklearn(autoencoder, initial_types=input_type, target_opset=17)
    (out_dir / AUTOENCODER_FILE).write_bytes(ae_onnx.SerializeToString())
    _check_export(out_dir / AUTOENCODER_FILE, autoencoder.predict(probe), probe, output=0)

    meta = {
        "version": MODEL_VERSION,
        "features": list(FEATURES),
        "classes": list(CLASSES),
        "classifier_file": CLASSIFIER_FILE,
        "autoencoder_file": AUTOENCODER_FILE,
        "healthy_cut": report["healthy_cut"],
        "novelty_threshold": report["novelty_threshold"],
        "evaluation": {
            "healthy_flag_rate": round(report["healthy_flag_rate"], 4),
            "detection_rate": {k: round(v, 4) for k, v in report["detection_rate"].items()},
            "named_correctly": {k: round(v, 4) for k, v in report["named_correctly"].items()},
            "unseen_pattern_detection": round(report["unseen_pattern_detection"], 4),
        },
        "trained_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": SEED,
    }
    (out_dir / META_FILE).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    classifier, autoencoder, report = train()
    export(classifier, autoencoder, report)
    print(f"Saved {CLASSIFIER_FILE}, {AUTOENCODER_FILE} and {META_FILE}")
    print(f"Healthy days flagged: {report['healthy_flag_rate']:.1%}")
    for pattern in PATTERNS:
        print(f"  {pattern:<12} detected {report['detection_rate'][pattern]:.1%}"
              f" · named correctly {report['named_correctly'][pattern]:.1%}")
    print(f"  unseen pattern detected {report['unseen_pattern_detection']:.1%}")


if __name__ == "__main__":
    main()
