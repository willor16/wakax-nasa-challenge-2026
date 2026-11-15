"""Clinical reference ranges loaded from ``db/seed_snapshots/reference_ranges.json``.

This is the single source of truth for every limit the app uses: the metric
catalog, alert severities, personal daily targets and sleep architecture.
Screens never hard-code thresholds; they classify through ``classify``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR
from app.services.alert_rules import MetricThresholds, Severity, classify_value

REFERENCE_PATH = BACKEND_DIR / "db" / "seed_snapshots" / "reference_ranges.json"

STATUS_BY_SEVERITY = {
    None: "NOMINAL",
    Severity.INFO: "WATCH",
    Severity.WARNING: "WARNING",
    Severity.CRITICAL: "CRITICAL",
}


@lru_cache(maxsize=1)
def load_reference(path: Path = REFERENCE_PATH) -> dict[str, Any]:
    """Parsed reference document (cached)."""
    return json.loads(path.read_text(encoding="utf-8"))


def metric_rows() -> list[dict[str, Any]]:
    """Catalog rows ready for ``metric_catalog`` with the source text resolved."""
    ref = load_reference()
    sources = ref["sources"]
    rows: list[dict[str, Any]] = []
    for metric in ref["metrics"]:
        row = {
            key: metric.get(key)
            for key in (
                "metric_key",
                "display_name_en",
                "category",
                "unit",
                "nominal_min",
                "nominal_max",
                "warning_min",
                "warning_max",
                "critical_min",
                "critical_threshold",
                "recommended_frequency_hours",
            )
        }
        row["clinical_reference"] = sources[metric["source"]]
        rows.append(row)
    return rows


@lru_cache(maxsize=1)
def _metric_index() -> dict[str, dict[str, Any]]:
    return {m["metric_key"]: m for m in load_reference()["metrics"]}


def metric(metric_key: str) -> dict[str, Any] | None:
    """Full reference entry for one metric, or None when unknown."""
    return _metric_index().get(metric_key)


def thresholds(metric_key: str) -> MetricThresholds | None:
    entry = metric(metric_key)
    if entry is None:
        return None
    return MetricThresholds(
        nominal_min=entry["nominal_min"],
        nominal_max=entry["nominal_max"],
        warning_min=entry.get("warning_min"),
        warning_max=entry.get("warning_max"),
        critical_min=entry.get("critical_min"),
        critical_threshold=entry.get("critical_threshold"),
    )


def classify(metric_key: str, value: float | None) -> Severity | None:
    """Severity of a value against the reference limits (None = nominal or unknown)."""
    if value is None:
        return None
    limits = thresholds(metric_key)
    return classify_value(value, limits) if limits else None


def status_label(metric_key: str, value: float | None) -> str:
    """``NOMINAL`` / ``WATCH`` / ``WARNING`` / ``CRITICAL``, or ``NO_DATA``."""
    if value is None:
        return "NO_DATA"
    return STATUS_BY_SEVERITY[classify(metric_key, value)]


def classify_relative(
    metric_key: str, value: float | None, baseline_mean: float | None
) -> Severity | None:
    """Severity for metrics judged as a share of the personal pre-flight value.

    Example: VO2 max under 80% of pre-flight is WARNING; bone density under
    93.8% (a 6.2% loss, the pelvis/lumbar reference) is CRITICAL.
    """
    entry = metric(metric_key)
    rule = (entry or {}).get("relative_to_baseline")
    if not rule or value is None or not baseline_mean:
        return None
    pct = value / baseline_mean * 100.0
    if "critical_below_pct" in rule and pct < rule["critical_below_pct"]:
        return Severity.CRITICAL
    if "warning_below_pct" in rule and pct < rule["warning_below_pct"]:
        return Severity.WARNING
    if "info_below_pct" in rule and pct < rule["info_below_pct"]:
        return Severity.INFO
    return None


HELP_FIELDS = ("summary_en", "interpretation_en", "operational_impact_en")


def help_entries() -> list[dict[str, Any]]:
    """Plain-language explanation for every parameter shown on screen.

    Catalog metrics carry their own help text and usual range; parameters that are not
    single catalog readings (sleep stages, check-in scores, test results, solar activity)
    come from ``help_topics``.
    """
    ref = load_reference()
    entries = [
        {
            "key": m["metric_key"],
            "label_en": m["display_name_en"],
            "unit": m["unit"],
            **{field: m[field] for field in HELP_FIELDS},
            "nominal_min": m["nominal_min"],
            "nominal_max": m["nominal_max"],
        }
        for m in ref["metrics"]
    ]
    entries.extend(
        {
            "key": t["key"],
            "label_en": t["label_en"],
            "unit": t["unit"],
            **{field: t[field] for field in HELP_FIELDS},
            "nominal_min": t.get("nominal_min"),
            "nominal_max": t.get("nominal_max"),
        }
        for t in ref.get("help_topics", [])
    )
    return entries


def is_plausible(metric_key: str, value: float) -> bool:
    """Reject physically impossible readings (typing errors such as HR 5000)."""
    entry = metric(metric_key)
    if entry is None:
        return True
    low, high = entry.get("plausible_min"), entry.get("plausible_max")
    return (low is None or value >= low) and (high is None or value <= high)


@dataclass(frozen=True, slots=True)
class PersonalTargets:
    hydration_ml: float
    calories_kcal: float
    exercise_min: float
    muscle_mass_kg: tuple[float, float]
    sleep_min: float


def _calorie_target(
    sex: str | None, age: int | None, weight_kg: float | None, height_cm: float | None
) -> float:
    cfg = load_reference()["personal_targets"]["calories"]
    for row in cfg["table"]:
        if row["sex"] == sex and age is not None and row["age_min"] <= age <= row["age_max"]:
            low, high = row["active"]
            return float(round((low + high) / 2))
    if weight_kg and height_cm and age:
        offset = 5 if sex == "M" else -161
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + offset
        return float(round(bmr * 1.55 / 50) * 50)
    return 2200.0


def personal_targets(crew: dict[str, Any], weight_kg: float | None) -> PersonalTargets:
    """Daily targets personalised by sex, age and body mass."""
    cfg = load_reference()["personal_targets"]
    sex = crew.get("sex") or "X"
    low_l, high_l = cfg["hydration"]["daily_l"].get(sex, cfg["hydration"]["daily_l"]["X"])
    if weight_kg:
        per_kg = weight_kg * sum(cfg["hydration"]["ml_per_kg"]) / 2
        hydration = min(max(per_kg, low_l * 1000), high_l * 1000)
    else:
        hydration = (low_l + high_l) / 2 * 1000
    muscle = cfg["muscle_mass_kg"].get(sex, cfg["muscle_mass_kg"]["M"])
    return PersonalTargets(
        hydration_ml=float(round(hydration / 50) * 50),
        calories_kcal=_calorie_target(sex, crew.get("age"), weight_kg, crew.get("height_cm")),
        exercise_min=float(cfg["exercise"]["session_min"]),
        muscle_mass_kg=(float(muscle[0]), float(muscle[1])),
        sleep_min=float(cfg["sleep_hours"][0] * 60),
    )


def sleep_reference() -> dict[str, Any]:
    return load_reference()["sleep"]


def radiation_reference() -> dict[str, Any]:
    return load_reference()["radiation"]
