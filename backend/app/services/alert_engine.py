"""Alert engine (D3-01): turns one stored measurement into zero or one ``alerts`` row.

Reads ``measurements``, ``metric_catalog``, ``baselines``, ``crew_members`` and
``mission`` (Quiet Hours), applies the pure rules in ``alert_rules`` and writes
the alert with three preventive care steps and a link to the medical guide.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from app.services import reference_ranges
from app.services.alert_rules import (
    TREND_READINGS,
    AlertDecision,
    Baseline,
    MetricThresholds,
    QuietHours,
    Severity,
    adverse_trend,
    build_alert_texts,
    decide,
    format_amount,
    is_role_focus,
    parse_utc,
    should_defer,
)
from app.services.reference_ranges import classify_relative, personal_targets

Step = dict[str, str]
# A repeat reading this close to an alert of the same metric is the follow-up the
# care steps ask for (or a trend already noted), not a new event. Urgent levels
# repeat sooner; a slow drift is reported once a week.
REPEAT_WINDOW = timedelta(hours=6)
REPEAT_WINDOWS = {
    Severity.CRITICAL: timedelta(hours=6),
    Severity.WARNING: timedelta(hours=24),
    Severity.INFO: timedelta(days=7),
}


def _step(title: str, detail: str) -> Step:
    return {"title_en": title, "detail_en": detail}


# Three preventive steps per group of metrics, shown in "Recommended Care".
CARE_STEPS: dict[str, list[Step]] = {
    "vision": [
        _step("Lower-Body Negative Pressure",
              "30-minute session at -25 mmHg before sleep to reduce headward fluid."),
        _step("Sleep Station Ventilation",
              "Keep sleep airflow at 85% with local CO2 below 3.0 mmHg."),
        _step("Scheduled Ultrasound",
              "Repeat the bilateral measurement with the Medical Officer within 3 days."),
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
        _step(
            "Complete today's resistance session", "Load-bearing exercise protects muscle and bone."
        ),
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
    "wellbeing": [
        _step(
            "Take a 10-minute break",
            "Step away from the task; slow breathing or the viewing window both help.",
        ),
        _step("Talk with a crewmate", "Share how the day is going; a short talk lowers the load."),
        _step(
            "Protect tonight's rest",
            "Keep the rest period free and dim the lights 30 minutes earlier.",
        ),
    ],
    "alertness": [
        _step("Repeat the test after a break", "Rest 15 minutes, drink water and try once more."),
        _step(
            "Hand over critical tasks", "Ask a crewmate to cover piloting or exterior work today."
        ),
        _step("Plan a full night of rest", "Aim for at least 7 hours before the next duty shift."),
    ],
    "radiation": [
        _step("Move to the shielded shelter", "Stay in the storm shelter until levels settle."),
        _step("Postpone exterior work", "Reschedule any spacewalk until the dose drops."),
        _step("Wear the personal dosimeter", "Keep it on during the whole shift."),
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
    "bp_diastolic_mmhg": "heart",
    "orthostatic_hr_delta_bpm": "heart",
    "respiratory_rate_brpm": "breathing",
    "cardiorespiratory_index": "breathing",
    "spo2_pct": "breathing",
    "vo2_max_ml_kg_min": "breathing",
    "body_temp_c": "temperature",
    "body_weight_kg": "body",
    "bmi_kg_m2": "body",
    "muscle_mass_kg": "body",
    "muscle_mass_retention_pct": "body",
    "bone_density_g_cm2": "body",
    "retinal_thickness_um": "vision",
    "hemoglobin_g_dl": "glucose",
    "urine_specific_gravity": "hydration",
    "urine_color_scale": "hydration",
    "blood_glucose_mg_dl": "glucose",
    "hydration_ml": "hydration",
    "exercise_min": "exercise",
    "calories_kcal": "nutrition",
    "ecg_lead_ii_mv": "heart",
    "height_cm": "body",
    "visual_acuity_snellen": "vision",
    "urine_protein_mg_dl": "hydration",
    "work_shift_min": "alertness",
    "eva_shift_min": "alertness",
    "cabin_co2_ppm": "cabin_air",
    "cabin_temp_c": "cabin_air",
    "cabin_humidity_pct": "cabin_air",
    "cabin_noise_dba": "cabin_air",
    "radiation_daily_msv": "radiation",
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
    "wellbeing": "wiki-sleep-01",
    "alertness": "wiki-sleep-01",
    "temperature": "wiki-co2-01",
    "hydration": "wiki-hydration-01",
    "radiation": "wiki-radiation-01",
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


def _has_open_alert(
    conn: sqlite3.Connection,
    crew_id: str,
    metric_key: str,
    severity: Severity,
    recorded_at_utc: str,
) -> bool:
    """True when a recent alert of this metric already says as much or more.

    The care steps ask the crew to measure again shortly after an alert. A
    repeat reading that is still out of range must not stack a copy of the same
    advisory; a worse reading (higher severity) or a reading after the repeat
    window for that severity still raises a new one. Unconfirmed alerts always
    count inside the window; confirmed ones count too, so a trend that was
    already read is not announced again every day.
    """
    rows = conn.execute(
        """
        SELECT a.severity, m.recorded_at_utc FROM alerts AS a
        JOIN measurements AS m ON m.id = a.measurement_id
        WHERE a.crew_id = ? AND m.metric_key = ?
        """,
        (crew_id, metric_key),
    ).fetchall()
    taken = parse_utc(recorded_at_utc)
    window = REPEAT_WINDOWS[severity]
    return any(
        Severity[r["severity"]] >= severity
        and abs(taken - parse_utc(r["recorded_at_utc"])) <= window
        for r in rows
    )


# Daily habits are judged on the day's running total against the crew member's
# own target (sex, age, body mass), not reading by reading.
HABIT_TARGETS = {
    "hydration_ml": "hydration_ml",
    "calories_kcal": "calories_kcal",
    "exercise_min": "exercise_min",
}
HABIT_NAMES = {
    "hydration_ml": "daily hydration goal",
    "calories_kcal": "daily nutrition goal",
    "exercise_min": "daily exercise goal",
}
EVENING_HOUR_UTC = 18


def _insert_alert(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    severity: Severity,
    title: str,
    message: str,
    group: str,
    deferred: bool,
) -> list[int]:
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
            severity.name,
            row["category"],
            title,
            message,
            json.dumps(care_steps(group, severity)),
            _guide_article_id(conn, group),
            int(deferred),
            datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )
    return [int(cursor.lastrowid)]


def _evaluate_habit(conn: sqlite3.Connection, row: sqlite3.Row, quiet: QuietHours) -> list[int]:
    """Reminder when the day's total is behind the personal target.

    Hydration is tracked through the day (under 90% of the goal is a WARNING,
    as dehydration raises kidney-stone risk in weightlessness). Meals and
    exercise are only judged from the evening on, once the day is nearly over.
    """
    metric_key, crew_id = row["metric_key"], row["crew_id"]
    taken = parse_utc(row["recorded_at_utc"])
    day = row["recorded_at_utc"][:10]
    if metric_key != "hydration_ml" and taken.hour < EVENING_HOUR_UTC:
        return []
    if metric_key == "exercise_min":
        eva = conn.execute(
            """SELECT 1 FROM measurements WHERE crew_id = ? AND metric_key = 'eva_shift_min'
               AND value_num > 0 AND substr(recorded_at_utc, 1, 10) = ?""",
            (crew_id, day),
        ).fetchone()
        if eva:
            return []  # exterior work replaces the exercise session that day
    total = (
        conn.execute(
            """SELECT SUM(value_num) FROM measurements WHERE crew_id = ? AND metric_key = ?
           AND substr(recorded_at_utc, 1, 10) = ? AND recorded_at_utc <= ?""",
            (crew_id, metric_key, day, row["recorded_at_utc"]),
        ).fetchone()[0]
        or 0.0
    )
    crew = conn.execute(
        "SELECT sex, age, height_cm FROM crew_members WHERE id = ?", (crew_id,)
    ).fetchone()
    weight = conn.execute(
        """SELECT value_num FROM measurements WHERE crew_id = ? AND metric_key = 'body_weight_kg'
           ORDER BY recorded_at_utc DESC, id DESC LIMIT 1""",
        (crew_id,),
    ).fetchone()
    target = getattr(
        personal_targets(dict(crew) if crew else {}, weight[0] if weight else None),
        HABIT_TARGETS[metric_key],
    )
    if metric_key == "calories_kcal":
        target *= 0.9  # within 10% of the energy goal counts as met
    if total >= target:
        return []
    severity = (
        Severity.WARNING
        if (metric_key == "hydration_ml" and total < target * 0.9)
        else Severity.INFO
    )
    already = conn.execute(
        """SELECT a.severity FROM alerts a JOIN measurements m ON m.id = a.measurement_id
           WHERE a.crew_id = ? AND m.metric_key = ? AND substr(m.recorded_at_utc, 1, 10) = ?""",
        (crew_id, metric_key, day),
    ).fetchall()
    if any(Severity[r["severity"]] >= severity for r in already):
        return []
    remaining = format_amount(target - total, row["unit"])
    title = f"{remaining} remaining to complete {HABIT_NAMES[metric_key]}"
    message = (
        f"Logged {format_amount(total, row['unit'])} of {format_amount(target, row['unit'])} today."
    )
    deferred = should_defer(severity, taken, quiet)
    message += (
        " This can wait until the rest period ends."
        if deferred
        else " Review preventive care on the right."
    )
    group = care_group(metric_key, row["category"])
    return _insert_alert(conn, row, severity, title, message, group, deferred)


def _evaluate_trend(
    conn: sqlite3.Connection, row: sqlite3.Row, reference: dict, quiet: QuietHours
) -> list[int]:
    """INFO advisory when the last three logged readings move steadily the harmful way
    (see ``adverse_trend``)."""
    readings = conn.execute(
        """SELECT value_num FROM measurements WHERE crew_id = ? AND metric_key = ?
           AND source_type = 'MANUAL' AND value_num IS NOT NULL AND recorded_at_utc <= ?
           ORDER BY recorded_at_utc DESC, id DESC LIMIT ?""",
        (row["crew_id"], row["metric_key"], row["recorded_at_utc"], TREND_READINGS),
    ).fetchall()
    values = [float(r["value_num"]) for r in reversed(readings)]
    baseline = None
    if row["mean_val"] is not None:
        baseline = Baseline(mean_val=row["mean_val"], std_dev=row["std_dev"],
                            sample_count=row["sample_count"])
    way = adverse_trend(values, reference.get("drift", "none"),
                        float(reference.get("drift_sd_floor") or 0.0), baseline)
    if way is None or _has_open_alert(
        conn, row["crew_id"], row["metric_key"], Severity.INFO, row["recorded_at_utc"]
    ):
        return []
    first, last = values[0], values[-1]
    title = (f"{row['display_name_en']} {'rising' if way == 'up' else 'falling'} steadily "
             f"({format_amount(last, row['unit'])})")
    message = (f"{'Up' if way == 'up' else 'Down'} over the last {TREND_READINGS} readings, "
               f"from {format_amount(first, row['unit'])}. Still inside the usual range; "
               "review preventive care on the right.")
    deferred = should_defer(Severity.INFO, parse_utc(row["recorded_at_utc"]), quiet)
    group = care_group(row["metric_key"], row["category"])
    return _insert_alert(conn, row, Severity.INFO, title, message, group, deferred)


def evaluate_measurement(conn: sqlite3.Connection, measurement_id: int) -> list[int]:
    """Evaluate a stored measurement and insert at most one alert. Returns new alert ids.

    Nothing is inserted while a recent alert of the same metric already covers
    this severity.
    """
    row = conn.execute(
        """
        SELECT
            m.id, m.crew_id, m.metric_key, m.value_num, m.recorded_at_utc,
            c.display_name_en, c.category, c.unit,
            c.nominal_min, c.nominal_max, c.warning_min, c.warning_max,
            c.critical_min, c.critical_threshold,
            b.mean_val, b.std_dev, b.sample_count,
            cm.role, cm.sex
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

    quiet = load_quiet_hours(conn)
    if row["metric_key"] in HABIT_TARGETS:
        return _evaluate_habit(conn, row, quiet)

    value = float(row["value_num"])
    # Sex-specific limits (haemoglobin, muscle mass) come from the reference ranges; the
    # catalog columns hold the shared range and remain the fallback.
    limits = reference_ranges.thresholds_for_crew(row["metric_key"], row["sex"])
    limits = limits or MetricThresholds(
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
    reference = reference_ranges.metric(row["metric_key"]) or {}

    decision = decide(
        value,
        limits,
        baseline,
        row["recorded_at_utc"],
        quiet=quiet,
        role_focus=is_role_focus(row["role"], row["metric_key"]),
        drift_direction=reference.get("drift", "both"),
        sd_floor=reference.get("drift_sd_floor", 0.0),
    )
    relative = classify_relative(row["metric_key"], value, baseline.mean_val if baseline else None)
    if relative is not None and (decision is None or relative > decision.severity):
        # Loss against the pre-flight value (aerobic capacity, bone, muscle, body mass).
        decision = AlertDecision(
            severity=relative,
            is_above=False,
            z=(value - baseline.mean_val) if baseline else None,
            is_quiet_deferred=should_defer(relative, parse_utc(row["recorded_at_utc"]), quiet),
        )
    if decision is None:
        # Inside the limits and the personal range, a steady move in the harmful direction
        # over the last readings is still worth a quiet note.
        return _evaluate_trend(conn, row, reference, quiet)
    if _has_open_alert(
        conn, row["crew_id"], row["metric_key"], decision.severity, row["recorded_at_utc"]
    ):
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
    return _insert_alert(
        conn, row, decision.severity, title, message, group, decision.is_quiet_deferred
    )


def raise_wellbeing_alert(
    conn: sqlite3.Connection,
    crew_id: str,
    severity: Severity,
    title: str,
    message: str,
    group: str,
    recorded_at_utc: str,
    category: str = "WELLBEING",
) -> int | None:
    """Advisory from a check-in or reaction test (no single measurement behind it).

    At most one per category and day, unless the new one is more severe.
    """
    day = recorded_at_utc[:10]
    existing = conn.execute(
        "SELECT severity FROM alerts WHERE crew_id = ? AND category = ? "
        "AND substr(created_at_utc, 1, 10) = ?",
        (crew_id, category, day),
    ).fetchall()
    if any(Severity[r["severity"]] >= severity for r in existing):
        return None
    deferred = should_defer(severity, parse_utc(recorded_at_utc), load_quiet_hours(conn))
    article = _guide_article_id(conn, group)
    cursor = conn.execute(
        """INSERT INTO alerts (crew_id, measurement_id, severity, category, title_en, message_en,
           recommended_actions_json, wiki_article_id, is_quiet_deferred, created_at_utc)
           VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            crew_id,
            severity.name,
            category,
            title,
            message,
            json.dumps(care_steps(group, severity)),
            article,
            int(deferred),
            recorded_at_utc,
        ),
    )
    return int(cursor.lastrowid)
