"""Crew profile for the Personal Data (04) and Physical (06) results screens.

Read-only: every number is a stored reading or is derived from stored readings
(BMI from mass and height, share of the pre-flight value, daily totals). When a
reading does not exist the field is ``None`` and the screen shows "No data".
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.services import habits, reference_ranges
from app.services.clinical_view import (
    assess,
    baseline,
    crew_row,
    day_total,
    latest,
    metric_view,
    payload,
    stage_averages,
    status_text,
)
from app.services.crew_metrics import evaluate_crew_readiness
from app.services.crew_names import display_title, short_name
from app.services.environment import cabin_snapshot
from app.services.mission_clock import (
    current_stage,
    day_label,
    mission_day,
    mission_elapsed_days,
    parse_iso,
)
from app.services.reference_ranges import personal_targets

RR_REFRACTORY_SEC = 0.25
SINUS_RATE = (40.0, 100.0)  # trained crew rest at 40-60 bpm, adults at 60-100 bpm



SEX_REFERENCE_TEXT = {
    "F": "Female ranges",
    "M": "Male ranges",
}

def analyse_ecg(samples: list[float], sample_rate_hz: float) -> dict[str, Any]:
    """Heart rate and beat-to-beat regularity from the R peaks of a Lead II strip."""
    if len(samples) < sample_rate_hz or not sample_rate_hz:
        return {"heart_rate_bpm": None, "rr_variation_pct": None, "rhythm_text": "No Signal"}
    threshold = max(samples) * 0.6
    refractory = int(sample_rate_hz * RR_REFRACTORY_SEC)
    peaks: list[int] = []
    for i in range(1, len(samples) - 1):
        if samples[i] >= threshold and samples[i] >= samples[i - 1] and samples[i] > samples[i + 1]:
            if not peaks or i - peaks[-1] > refractory:
                peaks.append(i)
    if len(peaks) < 3:
        return {"heart_rate_bpm": None, "rr_variation_pct": None, "rhythm_text": "Unclear Signal"}
    intervals = [(b - a) / sample_rate_hz for a, b in zip(peaks, peaks[1:], strict=False)]
    mean_rr = sum(intervals) / len(intervals)
    spread = (sum((x - mean_rr) ** 2 for x in intervals) / len(intervals)) ** 0.5
    rate = 60.0 / mean_rr
    variation = spread / mean_rr * 100
    if variation > 15:
        rhythm = "Irregular Rhythm"
    elif rate < SINUS_RATE[0]:
        rhythm = "Slow Rhythm"
    elif rate > SINUS_RATE[1]:
        rhythm = "Fast Rhythm"
    else:
        rhythm = "Normal Sinus"
    return {
        "heart_rate_bpm": round(rate),
        "rr_variation_pct": round(variation, 1),
        "rhythm_text": rhythm,
    }


def _biometrics(conn: sqlite3.Connection, crew: sqlite3.Row) -> list[dict[str, Any]]:
    crew_id = crew["id"]
    cards = []
    for key in ("height_cm", "body_weight_kg"):
        cards.append(metric_view(conn, crew_id, key, with_stages=True))

    weight, height = cards[1]["value"], cards[0]["value"] or crew["height_cm"]
    bmi_value = round(weight / (height / 100) ** 2, 1) if weight and height else None
    bmi_status, bmi_above = assess("bmi_kg_m2", bmi_value, None)
    bmi_ref = reference_ranges.metric("bmi_kg_m2") or {}
    base_weight = baseline(conn, crew_id, "body_weight_kg")
    base_height = baseline(conn, crew_id, "height_cm")
    cards.append(
        {
            "metric_key": "bmi_kg_m2",
            "label": "Body Mass Index",
            "unit": "kg/m²",
            "value": bmi_value,
            "status": bmi_status,
            "status_text": status_text(bmi_status, bmi_above),
            "baseline_mean": round(base_weight.mean_val / (base_height.mean_val / 100) ** 2, 1)
            if base_weight and base_height
            else None,
            "nominal_min": bmi_ref.get("nominal_min"),
            "nominal_max": bmi_ref.get("nominal_max"),
            "recorded_at_utc": cards[1]["recorded_at_utc"],
        }
    )
    for key in ("muscle_mass_kg", "bone_density_g_cm2", "vo2_max_ml_kg_min"):
        cards.append(metric_view(conn, crew_id, key, with_stages=True))
    low, high = personal_targets(dict(crew), weight).muscle_mass_kg
    cards[3]["reference_low"], cards[3]["reference_high"] = low, high
    # Skeletal muscle index: muscle mass against height, judged against the sex limit.
    cards[3]["smi"] = reference_ranges.smi(cards[3]["value"], height, crew["sex"])
    return cards


def _work(conn: sqlite3.Connection, crew_id: str, day: str) -> dict[str, Any]:
    shift = latest(conn, crew_id, "work_shift_min")
    details = payload(shift)
    eva_today = day_total(conn, crew_id, "eva_shift_min", day)
    eva_total = conn.execute(
        """SELECT SUM(value_num) FROM measurements WHERE crew_id = ?
           AND metric_key = 'eva_shift_min' AND mission_stage != 'LAUNCH'""",
        (crew_id,),
    ).fetchone()[0]
    is_today = bool(shift) and shift["recorded_at_utc"][:10] == day
    interior = int(shift["value_num"]) if is_today and details.get("mode") != "EVA" else None
    return {
        "interior_min": interior,
        "interior_location_en": details.get("location_en") if interior is not None else None,
        "exterior_min": int(eva_today) if eva_today is not None else 0,
        "exterior_mission_min": int(eva_total or 0),
        "mission_elapsed_days": mission_elapsed_days(conn),
    }


def _daily_rows(conn: sqlite3.Connection, crew: sqlite3.Row, day: str) -> list[dict[str, Any]]:
    """The six rows of "Daily Vitals, Exercise & Nutrition"."""
    crew_id = crew["id"]
    heart = metric_view(conn, crew_id, "resting_hr_bpm")
    systolic = metric_view(conn, crew_id, "bp_systolic_mmhg")
    diastolic = metric_view(conn, crew_id, "bp_diastolic_mmhg")
    order = ["NO_DATA", "NOMINAL", "WATCH", "WARNING", "CRITICAL"]
    worst = max((systolic, diastolic), key=lambda v: order.index(v["status"]))
    pressure = {
        "metric_key": "blood_pressure",
        "label": "Blood Pressure",
        "unit": "mmHg",
        "value": systolic["value"],
        "value_secondary": diastolic["value"],
        "status": worst["status"],
        "status_text": worst["status_text"],
        "baseline_mean": systolic["baseline_mean"],
        "baseline_secondary": diastolic["baseline_mean"],
        "baseline_low": systolic["baseline_low"],
        "baseline_high": systolic["baseline_high"],
        "nominal_min": systolic["nominal_min"],
        "nominal_max": systolic["nominal_max"],
        "scale_min": 70,
        "scale_max": 190,
        "recorded_at_utc": systolic["recorded_at_utc"],
    }
    heart["scale_min"], heart["scale_max"] = 30, 130
    oxygen = metric_view(conn, crew_id, "spo2_pct")
    oxygen["scale_min"], oxygen["scale_max"] = 85, 100

    summary = habits.day_habits(conn, crew_id, day)["habits"]
    names = {
        "exercise": ("exercise_min", "Daily Exercise"),
        "hydration": ("hydration_ml", "Hydration"),
        "nutrition": ("calories_kcal", "Caloric Intake"),
    }
    habit_rows = []
    for key in ("exercise", "hydration", "nutrition"):
        habit = summary[key]
        metric_key, label = names[key]
        value, target = habit["value"], habit["target"]
        done = habit["pct"] >= 100
        if value is None:
            status, text = "NO_DATA", "Not Logged"
        elif done:
            status, text = "NOMINAL", "On Track" if key == "exercise" else "Optimal"
        else:
            gap = target - value
            status = "WARNING" if (key == "hydration" and value < target * 0.9) else "WATCH"
            unit = habit["unit"]
            text = f"Low -{gap:,.0f} {unit}" if key != "exercise" else f"{gap:,.0f} min left"
        habit_rows.append(
            {
                "metric_key": metric_key,
                "label": habit["label"] if key == "exercise" else label,
                "unit": habit["unit"],
                "value": value,
                "target": target,
                "status": status,
                "status_text": text,
                "scale_min": 0,
                "scale_max": round(target * 1.3) if target else None,
                "nominal_min": target,
                "nominal_max": round(target * 1.3) if target else None,
            }
        )
    return [heart, pressure, oxygen, *habit_rows]


def _ecg(conn: sqlite3.Connection, crew_id: str) -> dict[str, Any] | None:
    row = latest(conn, crew_id, "ecg_lead_ii_mv")
    if row is None:
        return None
    data = payload(row)
    samples = data.get("samples") or []
    rate = data.get("sample_rate_hz") or 0
    analysis = analyse_ecg(samples, rate)
    hrv = latest(conn, crew_id, "hrv_rmssd_ms")
    temp = latest(conn, crew_id, "body_temp_c")
    return {
        "lead": data.get("lead", "II"),
        "paper_speed_mm_s": data.get("paper_speed_mm_s", 25),
        "sample_rate_hz": rate,
        "samples": samples,
        "recorded_at_utc": row["recorded_at_utc"],
        **analysis,
        "hrv_ms": hrv["value_num"] if hrv else None,
        "body_temp_c": temp["value_num"] if temp else None,
    }


def _labs(conn: sqlite3.Connection, crew_id: str) -> list[dict[str, Any]]:
    glucose = metric_view(conn, crew_id, "blood_glucose_mg_dl")
    glucose["title"] = "Blood Glucose"
    glucose["note"] = (
        f"Fasting check · Range {glucose['nominal_min']:g}–{glucose['nominal_max']:g} mg/dL"
    )
    blood = metric_view(conn, crew_id, "hemoglobin_g_dl", nominal_text="Normal")
    blood["title"] = "Blood Panel"
    blood["note"] = f"Hemoglobin · Range {blood['nominal_min']:g}–{blood['nominal_max']:g} g/dL"
    urine = metric_view(conn, crew_id, "urine_specific_gravity", nominal_text="Normal")
    urine["title"] = "Urine Specific Gravity"
    color = latest(conn, crew_id, "urine_color_scale")
    urine["note"] = (
        f"Weekly strip · Color level {color['value_num']:g} of 8"
        if color
        else f"Weekly strip · Range {urine['nominal_min']:.3f}–{urine['nominal_max']:.3f}"
    )

    from app.services.auscultation_service import cardiac_summary
    from app.services.vision_service import eye_views

    eyes = eye_views(conn, crew_id)
    heart = cardiac_summary(conn, crew_id)
    order = ["NO_DATA", "NOMINAL", "WATCH", "WARNING", "CRITICAL"]
    worst_eye = max(eyes.values(), key=lambda v: order.index(v["status"]))
    acuity = latest(conn, crew_id, "visual_acuity_snellen")
    parts = []
    if heart:
        parts.append(f"{heart['rhythm_text']} · {heart['sites_recorded']} of 4 sites")
    if worst_eye["value"] is not None:
        side = "Right" if worst_eye["metric_key"].endswith("right_mm") else "Left"
        parts.append(f"{side} optic sheath {worst_eye['value']:g} mm")
    eye_side = "Right Eye" if worst_eye["metric_key"].endswith("right_mm") else "Left Eye"
    combined = {
        "metric_key": "auscultation_vision",
        "title": "Auscultation & Vision",
        "value_text": " · ".join(
            filter(
                None,
                [
                    ("Regular" if heart and heart["regular"] else "Review") if heart else None,
                    f"20/{acuity['value_num']:g}" if acuity else None,
                ],
            )
        )
        or None,
        "status": worst_eye["status"],
        "status_text": (
            "Clear"
            if worst_eye["status"] == "NOMINAL"
            else f"{worst_eye['status_text']} · {eye_side}"
        )
        if worst_eye["status"] != "NO_DATA"
        else "No Data",
        "note": " · ".join(parts) or None,
    }
    return [glucose, blood, urine, combined]


def build_crew_profile(conn: sqlite3.Connection, crew_id: str) -> dict[str, Any] | None:
    crew = crew_row(conn, crew_id)
    if crew is None:
        return None
    day = habits.current_day(conn)
    readiness = evaluate_crew_readiness(conn, crew_id)
    weight = latest(conn, crew_id, "body_weight_kg")
    targets = personal_targets(dict(crew), weight["value_num"] if weight else None)
    hydration_today = day_total(conn, crew_id, "hydration_ml", day)
    daily = _daily_rows(conn, crew, day)
    scored = [row for row in daily if row["status"] != "NO_DATA"]
    return {
        "crew": {
            "id": crew["id"],
            "code": crew["code"],
            "full_name": crew["full_name"],
            "short_name": short_name(crew["full_name"]),
            "title_en": display_title(crew),
            "role": crew["role"],
            "age": crew["age"],
            "sex": crew["sex"],
            "blood_type": crew["blood_type"],
        },
        "reference_profile_en": SEX_REFERENCE_TEXT.get(crew["sex"] or "", "Shared adult ranges"),
        "mission_stage": current_stage(conn),
        "mission_day": mission_day(conn),
        "habits_day_label": day_label(mission_day(conn, parse_iso(f"{day}T00:00:00Z"))),
        "status": readiness["status"],
        "biometrics": _biometrics(conn, crew),
        "scan": {
            "core_temp": metric_view(conn, crew_id, "body_temp_c"),
            "hydration_ml": hydration_today,
            "hydration_target_ml": targets.hydration_ml,
        },
        "environment": cabin_snapshot(conn),
        "work": _work(conn, crew_id, day),
        "daily": daily,
        "on_target": sum(1 for row in scored if row["status"] == "NOMINAL"),
        "daily_count": len(daily),
        "ecg": _ecg(conn, crew_id),
        "labs": _labs(conn, crew_id),
        "stage_comparison": {
            key: stage_averages(conn, crew_id, key)
            for key in (
                "resting_hr_bpm",
                "body_weight_kg",
                "vo2_max_ml_kg_min",
                "optic_sheath_right_mm",
            )
        },
    }
