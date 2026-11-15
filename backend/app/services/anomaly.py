"""Onboard anomaly detection with the exported neural networks (D3-04).

Builds one "today" vector per crew member (latest reading of each model metric
as a z-score against the personal baseline), then runs the two CPU models
trained in ``backend/ml``: the pattern classifier and the novelty autoencoder.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import onnxruntime as ort

from app.config import BACKEND_DIR
from app.services.alert_rules import Baseline, z_score

MODELS_DIR = BACKEND_DIR / "models"
META_PATH = MODELS_DIR / "anomaly_models.json"
Z_LIMIT = 6.0

# Plain names shown to the physician, and the care group / guide article used
# to ground the suggestions (groups come from alert_engine.CARE_STEPS).
PATTERN_INFO: dict[str, dict[str, str]] = {
    "ocular": {"label_en": "Eye pressure and optic nerve changes", "group": "vision",
               "article": "wiki-vision-01"},
    "dehydration": {"label_en": "Signs of dehydration", "group": "hydration",
                    "article": "wiki-cardio-01"},
    "fatigue": {"label_en": "Fatigue and stress load", "group": "heart",
                "article": "wiki-sleep-01"},
    "low_oxygen": {"label_en": "Low blood oxygen", "group": "cabin_air",
                   "article": "wiki-co2-01"},
    "decoupled": {"label_en": "Unusual heart rhythm balance", "group": "heart",
                  "article": "wiki-cardio-01"},
    "novel": {"label_en": "Unusual combination of readings", "group": "heart",
              "article": "wiki-cardio-01"},
}


@dataclass(frozen=True)
class Models:
    meta: dict
    classifier: ort.InferenceSession
    autoencoder: ort.InferenceSession


@lru_cache(maxsize=1)
def load_models(meta_path: Path = META_PATH) -> Models:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    options = {"providers": ["CPUExecutionProvider"]}
    return Models(
        meta=meta,
        classifier=ort.InferenceSession(str(meta_path.parent / meta["classifier_file"]), **options),
        autoencoder=ort.InferenceSession(str(meta_path.parent / meta["autoencoder_file"]),
                                         **options),
    )


@dataclass
class Finding:
    crew_id: str
    anomaly_score: float
    is_anomaly: bool
    pattern: str | None
    pattern_label_en: str | None
    healthy_probability: float
    novelty_ratio: float
    top_metrics: list[dict] = field(default_factory=list)
    readings_used: int = 0
    model_name: str = ""


def crew_vector(conn: sqlite3.Connection, crew_id: str, features: list[str]
                ) -> tuple[np.ndarray, list[dict]]:
    """Latest z-score per model metric; missing data or baseline counts as 0 (usual)."""
    rows = conn.execute(
        """
        SELECT c.metric_key, c.display_name_en, c.unit, m.value_num,
               b.mean_val, b.std_dev, b.sample_count
        FROM metric_catalog AS c
        LEFT JOIN measurements AS m ON m.id = (
            SELECT id FROM measurements
            WHERE crew_id = ? AND metric_key = c.metric_key AND value_num IS NOT NULL
            ORDER BY recorded_at_utc DESC, id DESC LIMIT 1
        )
        LEFT JOIN baselines AS b ON b.crew_id = ? AND b.metric_key = c.metric_key
        """,
        (crew_id, crew_id),
    ).fetchall()
    by_key = {r["metric_key"]: r for r in rows}
    vector = np.zeros(len(features), dtype=np.float32)
    details: list[dict] = []
    for i, key in enumerate(features):
        row = by_key.get(key)
        if row is None or row["value_num"] is None or row["mean_val"] is None:
            continue
        z = z_score(float(row["value_num"]),
                    Baseline(row["mean_val"], row["std_dev"], row["sample_count"]))
        if z is None:
            continue
        vector[i] = max(-Z_LIMIT, min(Z_LIMIT, z))
        details.append({"metric_key": key, "display_name_en": row["display_name_en"],
                        "unit": row["unit"], "value": float(row["value_num"]),
                        "baseline": float(row["mean_val"]), "z": round(float(vector[i]), 2)})
    return vector, details


def detect(conn: sqlite3.Connection, crew_id: str, models: Models | None = None) -> Finding:
    """Run both networks on today's vector for one crew member."""
    models = models or load_models()
    meta = models.meta
    features = meta["features"]
    vector, details = crew_vector(conn, crew_id, features)
    batch = vector.reshape(1, -1)

    probabilities = models.classifier.run(None, {"z": batch})[1].reshape(-1)
    rebuilt = models.autoencoder.run(None, {"z": batch})[0].reshape(-1)
    residual = (vector - rebuilt) ** 2
    novelty_ratio = float(residual.mean() / meta["novelty_threshold"])

    healthy_probability = float(probabilities[0])
    cut = float(meta["healthy_cut"])
    pattern_ratio = (1.0 - healthy_probability) / max(1e-6, 1.0 - cut)
    by_pattern = healthy_probability < cut
    by_novelty = novelty_ratio >= 1.0

    pattern: str | None = None
    if by_pattern:
        pattern = meta["classes"][int(np.argmax(probabilities[1:])) + 1]
    elif by_novelty:
        pattern = "novel"

    # Metrics that explain the finding: biggest deviation, or worst rebuilt.
    weight = residual if pattern == "novel" else np.abs(vector)
    order = [features[i] for i in np.argsort(-weight) if weight[i] > 0]
    by_feature = {d["metric_key"]: d for d in details}
    top = [by_feature[k] for k in order if k in by_feature][:3]

    return Finding(
        crew_id=crew_id,
        anomaly_score=round(max(pattern_ratio, novelty_ratio), 3),
        is_anomaly=by_pattern or by_novelty,
        pattern=pattern,
        pattern_label_en=PATTERN_INFO[pattern]["label_en"] if pattern else None,
        healthy_probability=round(healthy_probability, 4),
        novelty_ratio=round(novelty_ratio, 3),
        top_metrics=top,
        readings_used=len(details),
        model_name=f"pattern-net+novelty-net v{meta['version']}",
    )
