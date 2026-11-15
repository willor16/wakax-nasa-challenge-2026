"""Reproducible simulated crew readings for training the anomaly model (D3-04).

Each sample is one day of a crew member's readings expressed as z-scores
against their own pre-flight baseline (the same scale the app computes from
``baselines``). Healthy days follow known physiological couplings; abnormal
days add the multi-signal patterns the crew physician cares about.

Couplings used for healthy days (correlation between z-scores):
* Resting heart rate vs heart rate variability: strongly inverse
  (Shaffer & Ginsberg, Front Public Health 5:258, 2017).
* Heart rate vs core temperature: about +10 beats per minute per degree C
  (Karjalainen & Viitasalo, Acta Med Scand 220:307-313, 1986).
* Heart rate vs systolic pressure and vs fluid intake: moderate.
* Left and right eye (optic nerve sheath, eye pressure): strongly linked, and
  sheath size moves with eye pressure (Mader et al., Ophthalmology
  118:2058-2069, 2011).

Abnormal patterns (added on top of a healthy day):
* ``ocular``: both optic nerve sheaths and eye pressures rise, the signature
  of spaceflight neuro-ocular changes (Mader 2011; Lee et al., npj
  Microgravity 6:7, 2020).
* ``dehydration``: heart rate and temperature up, fluid intake and systolic
  pressure down (Cheuvront & Kenefick, Compr Physiol 4:257-285, 2014).
* ``fatigue``: heart rate variability and exercise down, heart rate up
  (Thayer et al., Neurosci Biobehav Rev 36:747-756, 2012).
* ``low_oxygen``: blood oxygen down with a compensating heart rate rise.
* ``decoupled``: heart rate and heart rate variability rise together. Each value
  alone looks almost normal; only the broken coupling is abnormal, which is the
  case single-metric limits cannot catch.
"""

from __future__ import annotations

import numpy as np

FEATURES: tuple[str, ...] = (
    "resting_hr_bpm",
    "hrv_rmssd_ms",
    "spo2_pct",
    "bp_systolic_mmhg",
    "body_temp_c",
    "optic_sheath_left_mm",
    "optic_sheath_right_mm",
    "iop_left_mmhg",
    "iop_right_mmhg",
    "blood_glucose_mg_dl",
    "hydration_ml",
    "exercise_min",
)
_INDEX = {name: i for i, name in enumerate(FEATURES)}

_COUPLINGS: dict[tuple[str, str], float] = {
    ("resting_hr_bpm", "hrv_rmssd_ms"): -0.6,
    ("resting_hr_bpm", "body_temp_c"): 0.3,
    ("resting_hr_bpm", "bp_systolic_mmhg"): 0.3,
    ("resting_hr_bpm", "hydration_ml"): -0.25,
    ("hrv_rmssd_ms", "exercise_min"): 0.2,
    ("optic_sheath_left_mm", "optic_sheath_right_mm"): 0.8,
    ("iop_left_mmhg", "iop_right_mmhg"): 0.8,
    ("optic_sheath_left_mm", "iop_left_mmhg"): 0.3,
    ("optic_sheath_right_mm", "iop_right_mmhg"): 0.3,
    ("optic_sheath_left_mm", "iop_right_mmhg"): 0.25,
    ("optic_sheath_right_mm", "iop_left_mmhg"): 0.25,
}

# Shift ranges (in standard deviations) per abnormal pattern.
PATTERNS: dict[str, dict[str, tuple[float, float]]] = {
    "ocular": {
        "optic_sheath_left_mm": (2.5, 4.0), "optic_sheath_right_mm": (2.5, 4.0),
        "iop_left_mmhg": (1.5, 3.0), "iop_right_mmhg": (1.5, 3.0),
    },
    "dehydration": {
        "resting_hr_bpm": (2.0, 3.0), "body_temp_c": (1.5, 2.5),
        "hydration_ml": (-3.5, -2.5), "bp_systolic_mmhg": (-2.0, -1.0),
    },
    "fatigue": {
        "hrv_rmssd_ms": (-3.5, -2.5), "resting_hr_bpm": (1.5, 2.5),
        "exercise_min": (-3.0, -2.0),
    },
    "low_oxygen": {"spo2_pct": (-4.0, -3.0), "resting_hr_bpm": (1.5, 2.5)},
    "decoupled": {"resting_hr_bpm": (1.8, 2.4), "hrv_rmssd_ms": (1.8, 2.4)},
}


def correlation_matrix() -> np.ndarray:
    corr = np.eye(len(FEATURES))
    for (a, b), r in _COUPLINGS.items():
        corr[_INDEX[a], _INDEX[b]] = corr[_INDEX[b], _INDEX[a]] = r
    return corr


def healthy_days(n: int, rng: np.random.Generator) -> np.ndarray:
    """``n`` healthy days as z-scores with the physiological couplings above."""
    return rng.multivariate_normal(np.zeros(len(FEATURES)), correlation_matrix(), size=n)


def abnormal_days(pattern: str, n: int, rng: np.random.Generator) -> np.ndarray:
    """``n`` days showing one abnormal pattern."""
    days = healthy_days(n, rng)
    for feature, (low, high) in PATTERNS[pattern].items():
        days[:, _INDEX[feature]] += rng.uniform(low, high, size=n)
    return days


def build_dataset(seed: int = 7, n_train: int = 6000, n_val: int = 1500, n_test: int = 1500,
                  n_per_pattern: int = 300) -> dict[str, np.ndarray]:
    """Train/validation/test splits; abnormal days are only used for evaluation."""
    rng = np.random.default_rng(seed)
    data = {
        "train": healthy_days(n_train, rng),
        "val": healthy_days(n_val, rng),
        "test": healthy_days(n_test, rng),
    }
    for pattern in PATTERNS:
        data[f"abnormal_{pattern}"] = abnormal_days(pattern, n_per_pattern, rng)
    return {k: v.astype(np.float32) for k, v in data.items()}
