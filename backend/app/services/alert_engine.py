"""Alert engine (D3-01): turns one stored measurement into zero or one ``alerts`` row.

Reads ``measurements``, ``metric_catalog``, ``baselines``, ``crew_members`` and
``mission`` (Quiet Hours), applies the pure rules in ``alert_rules`` and writes
the alert with three preventive care steps and a link to the medical guide.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from app.services.alert_rules import (
    Baseline,
    MetricThresholds,
    QuietHours,
    Severity,
    build_alert_texts,
    decide,
    is_role_focus,
)

Step = dict[str, str]


def _step(title: str, detail: str) -> Step:
    return {"title_en": title, "detail_en": detail}


# Three preventive steps per group of metrics, shown in "Recommended Care".
CARE_STEPS: dict[str, list[Step]] = {
    "vision": [
        _step("Repeat the eye scan", "Measure both eyes again with the 3.0 mm guide."),
        _step("Lower-body negative pressure session (30 min)",
              "Helps shift fluid away from the head before rest."),
        _step("Keep the head raised", "Avoid head-down work and salty meals today."),
    ],
    "heart": [
        _step("Rest seated for 10 minutes", "Then measure again in a calm, quiet spot."),
        _step("Drink 400 mL of water", "Low fluid often speeds up the heartbeat."),
        _step("Pause hard exercise today", "Swap the next heavy session for light stretching."),
    ],
    "breathing": [
        _step("Relocate to a fresh air vent", "Sit near the main air duct for 20 minutes."),
        _step("Breathe slowly for 5 minutes", "In through the nose, out through the mouth."),
        _step("Measure again", "Repeat the reading after resting."),
    ],
    "temperature": [
        _step("Measure again in 30 minutes", "Use the same sensor and the same spot."),
        _step("Drink 400 mL of water", "Fluids help the body settle its temperature."),
        _step("Adjust clothing and rest", "Add or remove a layer and avoid hard work."),
    ],
    "body": [
        _step("Complete today's resistance session",
              "Load-bearing exercise protects muscle and bone."),
        _step("Meet protein and calcium goals", "Follow the meal plan for today."),
        _step("Recheck at the weekly scan", "Compare the result with this one."),
    ],
    "glucose": [
        _step("Measure again before the next meal", "Wash hands before the finger test."),
        _step("Choose a balanced meal", "Pair carbohydrates with protein and fiber."),
        _step("Log meals and medicines", "This helps the crew physician read the trend."),
    ],
    "hydration": [
        _step("Drink 400 mL of water now", "Spread the rest of the daily goal across the shift."),
        _step("Set a refill reminder", "Take a few sips every hour."),
        _step("Check again at the next break", "Log every drink as you go."),
    ],
    "exercise": [
        _step("Schedule the missing session", "Book time on the treadmill or cycle today."),
        _step("Start with 15 minutes", "A short session still protects heart and bone."),
        _step("Log the session", "Record minutes and effort when you finish."),
    ],
    "nutrition": [
        _step("Add a planned snack", "Pick one from today's meal plan."),
        _step("Log every meal", "Small gaps add up over the week."),
        _step("Check appetite tomorrow", "Tell the crew physician if it stays low."),
    ],
    "cabin_air": [
        _step("Check local airflow", "Make sure vents near the sleep station are open."),
        _step("Relocate to a fresh air vent", "Move to the main air duct and set the fan to 100%."),
        _step("Hydrate and reassess", "Drink 400 mL of water and check again in 30 minutes."),
    ],
}
URGENT_STEP = _step(
    "Call the crew physician now", "Share this reading and follow the medical guide steps."
)

METRIC_GROUP: dict[str, str] = {
    "optic_sheath_left_mm": "vision",
    "optic_sheath_right_mm": "vision",
    "iop_left_mmhg": "vision",
    "iop_right_mmhg": "vision",
    "resting_hr_bpm": "heart",
    "hrv_rmssd_ms": "heart",
    "bp_systolic_mmhg": "heart",
    "spo2_pct": "breathing",
    "vo2_max_ml_kg_min": "breathing",
    "body_temp_c": "temperature",
    "body_weight_kg": "body",
    "muscle_mass_retention_pct": "body",
    "bone_density_tscore": "body",
    "blood_glucose_mg_dl": "glucose",
    "hydration_ml": "hydration",
    "exercise_min": "exercise",
    "calories_kcal": "nutrition",
    "cabin_co2_ppm": "cabin_air",
}
# Fallback by catalog category for metrics added later.
CATEGORY_GROUP: dict[str, str] = {
    "VITALS": "heart",
    "BIOMETRICS": "body",
    "HABITS": "hydration",
    "LABS": "glucose",
    "VISION": "vision",
    "RESPIRATORY": "breathing",
    "ENVIRONMENT": "cabin_air",
}
# Medical guide article opened by "Open Medical Guide" for each group.
GROUP_GUIDE: dict[str, str] = {
    "vision": "wiki-vision-01",
    "heart": "wiki-cardio-01",
    "breathing": "wiki-cardio-01",
    "cabin_air": "wiki-co2-01",
}


def care_group(metric_key: str, category: str) -> str:
    """Group of care steps for a metric (explicit mapping first, then category)."""
    return METRIC_GROUP.get(metric_key) or CATEGORY_GROUP.get(category, "heart")


def care_steps(group: str, severity: Severity) -> list[Step]:
    """Three steps; for CRITICAL the last one is always a call to the physician."""
    steps = [dict(s) for s in CARE_STEPS[group]]
    if severity is Severity.CRITICAL:
        steps[-1] = dict(URGENT_STEP)
    return steps


def load_quiet_hours(conn: sqlite3.Connection) -> QuietHours:
    """Quiet Hours from the mission settings, or the 22:00-06:00 default."""
    row = conn.execute(
        "SELECT quiet_hours_start_utc, quiet_hours_end_utc FROM mission WHERE id = 1"
    ).fetchone()
    if row is None:
        return QuietHours()
    return QuietHours(start_utc=row["quiet_hours_start_utc"], end_utc=row["quiet_hours_end_utc"])


def _guide_article_id(conn: sqlite3.Connection, group: str) -> str | None:
    article_id = GROUP_GUIDE.get(group)
    if article_id is None:
        return None
    found = conn.execute("SELECT 1 FROM wiki_articles WHERE id = ?", (article_id,)).fetchone()
    return article_id if found else None


def evaluate_measurement(conn: sqlite3.Connection, measurement_id: int) -> list[int]:
    """Evaluate a stored measurement and insert at most one alert. Returns new alert ids."""
    row = conn.execute(
        """
        SELECT
            m.id, m.crew_id, m.metric_key, m.value_num, m.recorded_at_utc,
            c.display_name_en, c.category, c.unit,
            c.nominal_min, c.nominal_max, c.warning_min, c.warning_max,
            c.critical_min, c.critical_threshold,
            b.mean_val, b.std_dev, b.sample_count,
            cm.role
        FROM measurements AS m
        JOIN metric_catalog AS c ON c.metric_key = m.metric_key
        JOIN crew_members AS cm ON cm.id = m.crew_id
        LEFT JOIN baselines AS b ON b.crew_id = m.crew_id AND b.metric_key = m.metric_key
        WHERE m.id = ?
        """,
        (measurement_id,),
    ).fetchone()
    if row is None or row["value_num"] is None:
        return []

    value = float(row["value_num"])
    limits = MetricThresholds(
        nominal_min=row["nominal_min"],
        nominal_max=row["nominal_max"],
        warning_min=row["warning_min"],
        warning_max=row["warning_max"],
        critical_min=row["critical_min"],
        critical_threshold=row["critical_threshold"],
    )
    baseline = None
    if row["mean_val"] is not None:
        baseline = Baseline(
            mean_val=row["mean_val"], std_dev=row["std_dev"], sample_count=row["sample_count"]
        )

    decision = decide(
        value,
        limits,
        baseline,
        row["recorded_at_utc"],
        quiet=load_quiet_hours(conn),
        role_focus=is_role_focus(row["role"], row["metric_key"]),
    )
    if decision is None:
        return []

    title, message = build_alert_texts(
        row["display_name_en"],
        row["unit"],
        value,
        decision,
        limits,
        baseline_mean=baseline.mean_val if baseline else None,
        role=row["role"],
    )
    group = care_group(row["metric_key"], row["category"])
    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = conn.execute(
        """
        INSERT INTO alerts (
            crew_id, measurement_id, severity, category, title_en, message_en,
            recommended_actions_json, wiki_article_id, is_quiet_deferred, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["crew_id"],
            row["id"],
            decision.severity.name,
            row["category"],
            title,
            message,
            json.dumps(care_steps(group, decision.severity)),
            _guide_article_id(conn, group),
            int(decision.is_quiet_deferred),
            now_utc,
        ),
    )
    return [int(cursor.lastrowid)]
