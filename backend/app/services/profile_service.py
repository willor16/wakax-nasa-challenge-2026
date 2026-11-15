import json
import math
import sqlite3
from datetime import UTC, datetime
from typing import Any

from app.schemas.profile import (
    BiometricCardOut,
    BiometricScanOut,
    ClinicalLabCardOut,
    ClinicalProgressItemOut,
    CrewDemographicsOut,
    CrewProfileOut,
    DailyVitalsHabitsOut,
    EnvironmentAndWorkOut,
    EnvironmentGaugeOut,
    HudTagTone,
    LiveEcgOut,
    MissionStage,
    ProfileMissionContextOut,
    StageMetricSnapshotOut,
    StatusTone,
    WorkTimeRowOut,
)

ROLE_BADGE_MAP: dict[str, str] = {
    "PILOT": "FLIGHT PILOT",
    "OPERATOR": "MISSION OPERATOR",
    "PHYSICIAN": "FLIGHT PHYSICIAN",
    "ASTRONAUT": "MISSION SPECIALIST",
}

SEX_DISPLAY_MAP: dict[str, str] = {
    "F": "Female",
    "M": "Male",
    "X": "Non-Binary",
}

STATION_BY_ROLE: dict[str, str] = {
    "PILOT": "Command Bridge · Active Shift",
    "OPERATOR": "Systems Deck · Active Shift",
    "PHYSICIAN": "Medical Bay · Active Shift",
    "ASTRONAUT": "Science Lab · Active Shift",
}


def _short_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}".upper()
    return full_name.upper()


def _parse_iso_utc(raw: str | None) -> datetime | None:
    if not raw:
        return None
    normalized = raw.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _clamp(val: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, val)), 1)


def _format_hm_from_minutes(total_minutes: float) -> str:
    mins = max(0, int(round(total_minutes)))
    return f"{mins // 60}h {mins % 60:02d}m"


def _compute_z_score(
    value: float, baseline_mean: float | None, baseline_std: float | None
) -> float | None:
    if baseline_mean is None or baseline_std is None or baseline_std <= 0:
        return None
    return round((value - baseline_mean) / baseline_std, 2)


def _generate_lead_ii_waveform(
    hr_bpm: float, hrv_ms: float, sample_count: int = 250, sample_rate_hz: int = 100
) -> list[float]:
    clamped_hr = max(42.0, min(160.0, hr_bpm))
    rr_sec = 60.0 / clamped_hr
    jitter_ratio = min(0.035, max(0.0, (hrv_ms - 30.0) * 0.0004))
    samples: list[float] = []

    for idx in range(sample_count):
        t = idx / sample_rate_hz
        beat_idx = int(t / rr_sec)
        local_rr = rr_sec * (1.0 + (jitter_ratio if beat_idx % 2 == 0 else -jitter_ratio))
        phase = (t % local_rr) / local_rr

        p_wave = 0.14 * math.exp(-((phase - 0.16) ** 2) / (2.0 * 0.024**2))
        q_wave = -0.13 * math.exp(-((phase - 0.285) ** 2) / (2.0 * 0.009**2))
        r_wave = 1.18 * math.exp(-((phase - 0.31) ** 2) / (2.0 * 0.011**2))
        s_wave = -0.26 * math.exp(-((phase - 0.338) ** 2) / (2.0 * 0.010**2))
        t_wave = 0.28 * math.exp(-((phase - 0.54) ** 2) / (2.0 * 0.042**2))
        baseline_wander = 0.015 * math.sin(2.0 * math.pi * 0.25 * t)

        mv = round(p_wave + q_wave + r_wave + s_wave + t_wave + baseline_wander, 4)
        samples.append(mv)

    return samples


def _fetch_latest_by_metric(
    conn: sqlite3.Connection, crew_id: str, stage: MissionStage | None
) -> dict[str, dict[str, Any]]:
    if stage is not None:
        rows = conn.execute(
            """
            SELECT m.metric_key, m.value_num, m.payload_json, m.recorded_at_utc, m.mission_stage
            FROM measurements m
            INNER JOIN (
                SELECT metric_key, MAX(id) AS max_id
                FROM measurements
                WHERE crew_id = ? AND mission_stage = ?
                GROUP BY metric_key
            ) latest ON latest.max_id = m.id
            """,
            (crew_id, stage),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT m.metric_key, m.value_num, m.payload_json, m.recorded_at_utc, m.mission_stage
            FROM measurements m
            INNER JOIN (
                SELECT metric_key, MAX(id) AS max_id
                FROM measurements
                WHERE crew_id = ?
                GROUP BY metric_key
            ) latest ON latest.max_id = m.id
            """,
            (crew_id,),
        ).fetchall()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
            if not isinstance(payload, dict):
                payload = {}
        except ValueError:
            payload = {}
        result[str(row["metric_key"])] = {
            "value_num": float(row["value_num"]) if row["value_num"] is not None else None,
            "payload": payload,
            "recorded_at_utc": str(row["recorded_at_utc"]),
            "mission_stage": str(row["mission_stage"]),
        }
    return result


def _fetch_baselines(conn: sqlite3.Connection, crew_id: str) -> dict[str, tuple[float, float]]:
    rows = conn.execute(
        "SELECT metric_key, mean_val, std_dev FROM baselines WHERE crew_id = ?",
        (crew_id,),
    ).fetchall()
    return {str(r["metric_key"]): (float(r["mean_val"]), float(r["std_dev"])) for r in rows}


def _build_stage_comparison(
    conn: sqlite3.Connection, crew_id: str
) -> list[StageMetricSnapshotOut]:
    stages: tuple[MissionStage, ...] = ("LAUNCH", "MISSION", "RETURN")
    snapshots: list[StageMetricSnapshotOut] = []
    for st in stages:
        stage_map = _fetch_latest_by_metric(conn, crew_id, st)
        snapshots.append(
            StageMetricSnapshotOut(
                stage=st,
                has_records=len(stage_map) > 0,
                body_weight_kg=(stage_map.get("body_weight_kg") or {}).get("value_num"),
                resting_hr_bpm=(stage_map.get("resting_hr_bpm") or {}).get("value_num"),
                vo2_max_ml_kg_min=(stage_map.get("vo2_max_ml_kg_min") or {}).get("value_num"),
                optic_sheath_right_mm=(stage_map.get("optic_sheath_right_mm") or {}).get(
                    "value_num"
                ),
            )
        )
    return snapshots


def build_crew_profile(
    conn: sqlite3.Connection,
    crew_id: str,
    stage: MissionStage | None = None,
) -> CrewProfileOut | None:
    crew_row = conn.execute(
        """
        SELECT id, code, full_name, role, age, sex, blood_type, height_cm
        FROM crew_members
        WHERE id = ? AND is_active = 1
        """,
        (crew_id,),
    ).fetchone()
    if crew_row is None:
        return None

    mission_row = conn.execute("SELECT * FROM mission WHERE id = 1").fetchone()
    current_stage: MissionStage = (
        mission_row["current_stage"] if mission_row else "MISSION"
    )
    selected_stage: MissionStage = stage if stage is not None else current_stage

    stage_metrics = _fetch_latest_by_metric(conn, crew_id, stage)
    stage_has_records = len(stage_metrics) > 0
    fallback_metrics = (
        stage_metrics if stage_has_records else _fetch_latest_by_metric(conn, crew_id, None)
    )
    baselines = _fetch_baselines(conn, crew_id)

    now_dt = datetime.now(UTC)
    now_utc = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    launch_dt = _parse_iso_utc(mission_row["launch_utc"] if mission_row else None)
    latest_recorded_dt: datetime | None = None
    for item in fallback_metrics.values():
        ts_dt = _parse_iso_utc(item.get("recorded_at_utc"))
        if ts_dt and (latest_recorded_dt is None or ts_dt > latest_recorded_dt):
            latest_recorded_dt = ts_dt

    ref_dt = latest_recorded_dt or now_dt
    if launch_dt is not None:
        mission_day = max(1, (ref_dt.date() - launch_dt.date()).days + 1)
    else:
        mission_day = 45

    baseline_height = float(crew_row["height_cm"] or 172.0)
    sex_code = str(crew_row["sex"]) if crew_row["sex"] else None
    crew_role = str(crew_row["role"])

    def metric_val(key: str, default: float) -> float:
        entry = fallback_metrics.get(key)
        if entry and entry["value_num"] is not None:
            return float(entry["value_num"])
        base = baselines.get(key)
        if base is not None:
            return base[0]
        return default

    def base_pair(key: str, default_mean: float, default_std: float) -> tuple[float, float]:
        return baselines.get(key, (default_mean, default_std))

    if selected_stage == "MISSION":
        active_height = round(baseline_height + 2.2, 1)
    elif selected_stage == "RETURN":
        active_height = round(baseline_height + 0.5, 1)
    else:
        active_height = round(baseline_height, 1)

    weight_kg = round(metric_val("body_weight_kg", 68.0), 1)
    weight_base, weight_std = base_pair("body_weight_kg", weight_kg, 1.5)

    explicit_bmi = fallback_metrics.get("bmi_kg_m2")
    if explicit_bmi and explicit_bmi["value_num"] is not None:
        bmi_val = round(float(explicit_bmi["value_num"]), 1)
    else:
        bmi_val = round(weight_kg / ((active_height / 100.0) ** 2), 1)
    bmi_base = round(weight_base / ((baseline_height / 100.0) ** 2), 1)

    muscle_ret_pct = round(metric_val("muscle_mass_retention_pct", 98.0), 1)
    muscle_base, muscle_std = base_pair("muscle_mass_retention_pct", 100.0, 2.0)
    smm_ratio = 0.445 if sex_code == "F" else 0.475
    muscle_kg = round(weight_base * smm_ratio * (muscle_ret_pct / 100.0), 1)

    bone_tscore = round(metric_val("bone_density_tscore", 0.3), 2)
    bone_base_t, bone_std_t = base_pair("bone_density_tscore", 0.4, 0.2)
    bmd_gcm2 = round(1.16 + 0.11 * bone_tscore, 2)
    bmd_base_gcm2 = max(0.8, 1.16 + 0.11 * bone_base_t)
    bmd_pct_of_base = round((bmd_gcm2 / bmd_base_gcm2) * 100.0, 1)

    vo2_val = round(metric_val("vo2_max_ml_kg_min", 46.0), 1)
    vo2_base, vo2_std = base_pair("vo2_max_ml_kg_min", 48.0, 2.0)

    bmi_tone: StatusTone = (
        "critical"
        if (bmi_val < 17.0 or bmi_val > 31.0)
        else ("warn" if (bmi_val < 18.5 or bmi_val > 26.5) else "nominal")
    )
    muscle_tone: StatusTone = (
        "critical"
        if muscle_ret_pct < 85.0
        else ("warn" if muscle_ret_pct < 92.0 else "nominal")
    )
    bone_tone: StatusTone = (
        "critical"
        if bone_tscore <= -2.0
        else ("warn" if bone_tscore < -1.0 else "nominal")
    )
    vo2_tone: StatusTone = (
        "critical" if vo2_val < 30.0 else ("warn" if vo2_val < 38.0 else "nominal")
    )
    weight_delta_pct = abs(weight_kg - weight_base) / max(weight_base, 1.0) * 100.0
    weight_tone: StatusTone = (
        "critical"
        if weight_delta_pct >= 10.0
        else ("warn" if weight_delta_pct >= 5.0 else "nominal")
    )

    biometrics: list[BiometricCardOut] = [
        BiometricCardOut(
            key="height_cm",
            label="HEIGHT",
            value=active_height,
            display_value=f"{active_height:.1f} cm",
            unit="cm",
            baseline_mean=round(baseline_height, 1),
            baseline_std=0.5,
            z_score=_compute_z_score(active_height, baseline_height, 1.2),
            subtitle=f"Baseline: {baseline_height:.1f} cm",
            status_tone="nominal",
        ),
        BiometricCardOut(
            key="body_weight_kg",
            label="WEIGHT",
            value=weight_kg,
            display_value=f"{weight_kg:.1f} kg",
            unit="kg",
            baseline_mean=round(weight_base, 1),
            baseline_std=round(weight_std, 2),
            z_score=_compute_z_score(weight_kg, weight_base, weight_std),
            subtitle=f"Baseline: {weight_base:.1f} kg",
            status_tone=weight_tone,
        ),
        BiometricCardOut(
            key="bmi_kg_m2",
            label="BODY MASS INDEX",
            value=bmi_val,
            display_value=f"{bmi_val:.1f}",
            unit="kg/m²",
            baseline_mean=bmi_base,
            baseline_std=0.8,
            z_score=_compute_z_score(bmi_val, bmi_base, 0.8),
            subtitle="Normal: 19.5–24.9",
            status_tone=bmi_tone,
        ),
        BiometricCardOut(
            key="muscle_mass_retention_pct",
            label="MUSCLE MASS",
            value=muscle_kg,
            display_value=f"{muscle_kg:.1f} kg",
            unit="kg",
            baseline_mean=round(muscle_base, 1),
            baseline_std=round(muscle_std, 2),
            z_score=_compute_z_score(muscle_ret_pct, muscle_base, muscle_std),
            subtitle=f"{muscle_ret_pct:.1f}% retained",
            status_tone=muscle_tone,
        ),
        BiometricCardOut(
            key="bone_density_tscore",
            label="BONE DENSITY",
            value=bmd_gcm2,
            display_value=f"{bmd_gcm2:.2f} g/cm²",
            unit="g/cm²",
            baseline_mean=round(bone_base_t, 2),
            baseline_std=round(bone_std_t, 2),
            z_score=_compute_z_score(bone_tscore, bone_base_t, bone_std_t),
            subtitle=f"{bmd_pct_of_base:.1f}% of baseline",
            status_tone=bone_tone,
        ),
        BiometricCardOut(
            key="vo2_max_ml_kg_min",
            label="AEROBIC CAPACITY",
            value=vo2_val,
            display_value=f"{vo2_val:.1f} mL/kg",
            unit="mL/kg/min",
            baseline_mean=round(vo2_base, 1),
            baseline_std=round(vo2_std, 2),
            z_score=_compute_z_score(vo2_val, vo2_base, vo2_std),
            subtitle=(
                "Optimal range" if vo2_tone == "nominal" else f"Baseline: {vo2_base:.1f} mL/kg"
            ),
            status_tone=vo2_tone,
        ),
    ]

    resting_hr = round(metric_val("resting_hr_bpm", 64.0), 1)
    hr_base, hr_std = base_pair("resting_hr_bpm", 62.0, 4.0)
    hrv_ms = round(metric_val("hrv_rmssd_ms", 62.0), 1)
    spo2_pct = round(metric_val("spo2_pct", 98.0), 1)
    bp_sys = round(metric_val("bp_systolic_mmhg", 118.0))
    bp_sys_base, _ = base_pair("bp_systolic_mmhg", 114.0, 5.0)
    bp_dia_entry = fallback_metrics.get("bp_diastolic_mmhg")
    if bp_dia_entry and bp_dia_entry["value_num"] is not None:
        bp_dia = round(float(bp_dia_entry["value_num"]))
    else:
        bp_dia = round(bp_sys * 0.64)
    bp_dia_base = round(bp_sys_base * 0.64)

    body_temp_c = round(metric_val("body_temp_c", 36.7), 1)
    hydration_ml = round(metric_val("hydration_ml", 2450.0))
    hydration_target_ml = 2800
    hydration_liters = round(hydration_ml / 1000.0, 1)
    hydration_target_liters = 2.8

    exercise_min = round(metric_val("exercise_min", 85.0))
    exercise_target_min = 90
    calories_kcal = round(metric_val("calories_kcal", 2420.0))
    calories_base, _ = base_pair("calories_kcal", 2500.0, 120.0)
    calories_target = int(round(calories_base / 50.0) * 50)

    optic_left = round(metric_val("optic_sheath_left_mm", 4.5), 2)
    optic_right = round(metric_val("optic_sheath_right_mm", 4.6), 2)
    max_optic = max(optic_left, optic_right)

    cardiac_tone: StatusTone = (
        "critical"
        if (resting_hr >= 110 or resting_hr < 40 or bp_sys >= 160)
        else ("warn" if (resting_hr > 90 or bp_sys > 135 or hrv_ms < 30) else "nominal")
    )
    pulmonary_tone: StatusTone = (
        "critical" if spo2_pct < 90.0 else ("warn" if spo2_pct < 95.0 else "nominal")
    )
    ocular_tone: StatusTone = (
        "critical" if max_optic >= 5.8 else ("warn" if max_optic >= 5.2 else "nominal")
    )

    if "critical" in (cardiac_tone, pulmonary_tone, ocular_tone) or body_temp_c >= 38.5:
        scan_label = "CRITICAL"
        scan_tone: HudTagTone = "critical"
    elif "warn" in (cardiac_tone, pulmonary_tone, ocular_tone) or body_temp_c >= 37.6:
        scan_label = "ATTENTION"
        scan_tone = "warn"
    else:
        scan_label = "NOMINAL"
        scan_tone = "reference"

    biometric_scan = BiometricScanOut(
        scan_label=scan_label,
        scan_tone=scan_tone,
        core_temp_c=body_temp_c,
        core_temp_display=f"{body_temp_c:.1f} °C",
        hydration_liters=hydration_liters,
        hydration_target_liters=hydration_target_liters,
        hydration_display=f"{hydration_liters:.1f} / {hydration_target_liters:.1f} L",
        cardiac_tone=cardiac_tone,
        pulmonary_tone=pulmonary_tone,
        ocular_tone=ocular_tone,
    )

    env_row = conn.execute(
        "SELECT * FROM environment_readings ORDER BY id DESC LIMIT 1"
    ).fetchone()
    temp_c = round(float(env_row["temp_c"]), 1) if env_row else 21.8
    humidity_pct = round(float(env_row["humidity_pct"])) if env_row else 44
    noise_dba = round(float(env_row["noise_dba"])) if env_row else 48
    co2_ppm = round(float(env_row["co2_ppm"]), 1) if env_row else 1120.0
    radiation_msv = round(float(env_row["radiation_msv"]), 2) if env_row else 0.45
    solar_flag = bool(env_row["solar_event_flag"]) if env_row else False
    co2_mmhg = round((co2_ppm / 1_000_000.0) * 760.0, 2)

    work_rows_db = conn.execute(
        """
        SELECT value_num, payload_json, recorded_at_utc
        FROM measurements
        WHERE crew_id = ? AND metric_key = 'work_shift_min'
        ORDER BY id DESC
        LIMIT 30
        """,
        (crew_id,),
    ).fetchall()

    latest_iva_min = 320.0
    latest_eva_min = 0.0
    cumulative_eva_min = 760.0
    if work_rows_db:
        iva_found = False
        eva_found = False
        eva_sum = 0.0
        for wr in work_rows_db:
            w_val = float(wr["value_num"] or 0.0)
            try:
                w_payload = json.loads(wr["payload_json"])
            except ValueError:
                w_payload = {}
            mode = str(w_payload.get("shift_mode", "IVA")).upper()
            if mode == "EVA":
                eva_sum += w_val
                if not eva_found:
                    latest_eva_min = w_val
                    eva_found = True
            elif not iva_found:
                latest_iva_min = w_val
                iva_found = True
        if eva_sum > 0:
            cumulative_eva_min = 760.0 + eva_sum

    co2_tone: StatusTone = (
        "critical" if co2_ppm >= 4000.0 else ("warn" if co2_ppm >= 2500.0 else "nominal")
    )
    noise_tone: StatusTone = (
        "critical" if noise_dba >= 70 else ("warn" if noise_dba >= 55 else "nominal")
    )
    temp_tone: StatusTone = (
        "warn" if (temp_c < 18.5 or temp_c > 25.5) else "nominal"
    )
    hum_tone: StatusTone = (
        "warn" if (humidity_pct < 30 or humidity_pct > 65) else "nominal"
    )

    environment_work = EnvironmentAndWorkOut(
        habitat_tag="HABITAT A",
        co2_ppm=co2_ppm,
        co2_mmhg=co2_mmhg,
        radiation_msv=radiation_msv,
        solar_event_flag=solar_flag,
        gauges=[
            EnvironmentGaugeOut(
                key="temp_c",
                label="TEMPERATURE",
                value=temp_c,
                display_value=f"{temp_c:.1f}",
                subtitle="°C",
                arc_pct=_clamp(((temp_c - 15.0) / 15.0) * 100.0),
                status_tone=temp_tone,
            ),
            EnvironmentGaugeOut(
                key="humidity_pct",
                label="HUMIDITY",
                value=float(humidity_pct),
                display_value=f"{humidity_pct}%",
                subtitle="Optimal 40–55%",
                arc_pct=_clamp(float(humidity_pct)),
                status_tone=hum_tone,
            ),
            EnvironmentGaugeOut(
                key="noise_dba",
                label="AMBIENT NOISE",
                value=float(noise_dba),
                display_value=f"{noise_dba}",
                subtitle="dBA (<55 dBA)",
                arc_pct=_clamp((float(noise_dba) / 80.0) * 100.0),
                status_tone=noise_tone,
            ),
            EnvironmentGaugeOut(
                key="co2_mmhg",
                label="CABIN CO₂",
                value=co2_mmhg,
                display_value=f"{co2_mmhg:.1f}",
                subtitle="mmHg (<4.0)",
                arc_pct=_clamp((co2_ppm / 4000.0) * 100.0),
                status_tone=co2_tone,
            ),
        ],
        work_header=f"WORK TIME · DAY {mission_day:03d}",
        work_rows=[
            WorkTimeRowOut(
                key="iva",
                label="INTERIOR WORK (IVA)",
                subtitle=STATION_BY_ROLE.get(crew_role, "Habitat Operations · Active Shift"),
                display_value=_format_hm_from_minutes(latest_iva_min),
                status_tone="warn" if latest_iva_min > 540 else "nominal",
            ),
            WorkTimeRowOut(
                key="eva",
                label="EXTERIOR WORK (EVA)",
                subtitle=f"Mission Cumulative: {_format_hm_from_minutes(cumulative_eva_min)}",
                display_value=_format_hm_from_minutes(latest_eva_min),
                status_tone="warn" if latest_eva_min > 360 else "nominal",
            ),
            WorkTimeRowOut(
                key="met",
                label="MISSION ELAPSED TIME",
                subtitle=f"{now_dt.strftime('%H:%M')} UTC · Schedule Nominal",
                display_value=f"{mission_day} Days",
                status_tone="nominal",
            ),
        ],
    )

    hr_low = int(round(max(48.0, hr_base - max(hr_std * 2.0, 5.0))))
    hr_high = int(round(min(90.0, hr_base + max(hr_std * 2.0, 7.0))))
    hr_on_target = 50.0 <= resting_hr <= 85.0
    hr_tone: StatusTone = (
        "critical"
        if (resting_hr < 40.0 or resting_hr >= 110.0)
        else ("nominal" if hr_on_target else "warn")
    )

    bp_on_target = (95 <= bp_sys <= 130) and (60 <= bp_dia <= 85)
    bp_tone: StatusTone = (
        "critical"
        if (bp_sys >= 160 or bp_dia >= 105)
        else ("nominal" if bp_on_target else "warn")
    )

    spo2_on_target = spo2_pct >= 96.0
    spo2_tone: StatusTone = (
        "critical" if spo2_pct < 90.0 else ("nominal" if spo2_on_target else "warn")
    )

    ex_on_target = exercise_min >= 75
    ex_tone: StatusTone = (
        "critical" if exercise_min < 25 else ("nominal" if ex_on_target else "warn")
    )
    ex_label = (
        "Optimal"
        if exercise_min >= exercise_target_min
        else ("On Track" if ex_on_target else "Low")
    )

    hyd_rem_ml = max(0, hydration_target_ml - hydration_ml)
    hyd_on_target = hydration_ml >= 2600
    hyd_tone: StatusTone = (
        "critical"
        if hydration_ml < 1400
        else ("nominal" if hyd_on_target else "warn")
    )
    hyd_status = "Optimal" if hyd_rem_ml == 0 else (
        "On Track" if hyd_on_target else f"Low -{hyd_rem_ml}mL"
    )
    hyd_subtitle = (
        f"Daily target: 2.8 L ({hyd_rem_ml} mL remaining)"
        if hyd_rem_ml > 0
        else "Daily target: 2.8 L (Target met)"
    )

    cal_on_target = abs(calories_kcal - calories_target) <= 350 and calories_kcal >= 2000
    cal_tone: StatusTone = (
        "critical" if calories_kcal < 1500 else ("nominal" if cal_on_target else "warn")
    )

    vitals_items: list[ClinicalProgressItemOut] = [
        ClinicalProgressItemOut(
            key="resting_hr_bpm",
            label="Resting Heart Rate",
            subtitle=f"Baseline: {hr_low}–{hr_high} bpm",
            display_value=f"{round(resting_hr)}",
            unit="bpm",
            status_label="Normal" if hr_on_target else "Elevated",
            status_tone=hr_tone,
            progress_pct=_clamp(((resting_hr - 40.0) / 70.0) * 100.0),
            band_start_pct=_clamp(((hr_low - 40.0) / 70.0) * 100.0),
            band_width_pct=_clamp(((hr_high - hr_low) / 70.0) * 100.0, 12.0, 65.0),
            on_target=hr_on_target,
        ),
        ClinicalProgressItemOut(
            key="blood_pressure",
            label="Blood Pressure",
            subtitle=f"Baseline: {round(bp_sys_base)}/{bp_dia_base} mmHg",
            display_value=f"{bp_sys}/{bp_dia}",
            unit="mmHg",
            status_label="Optimal" if bp_on_target else "Elevated",
            status_tone=bp_tone,
            progress_pct=_clamp(((bp_sys - 85.0) / 75.0) * 100.0),
            band_start_pct=_clamp(((95.0 - 85.0) / 75.0) * 100.0),
            band_width_pct=_clamp(((130.0 - 95.0) / 75.0) * 100.0),
            on_target=bp_on_target,
        ),
        ClinicalProgressItemOut(
            key="spo2_pct",
            label="Oxygen Saturation (SpO₂)",
            subtitle="Nominal range: 96–100%",
            display_value=f"{round(spo2_pct)}",
            unit="%",
            status_label="Optimal" if spo2_on_target else "Low",
            status_tone=spo2_tone,
            progress_pct=_clamp(((spo2_pct - 88.0) / 12.0) * 100.0),
            band_start_pct=_clamp(((96.0 - 88.0) / 12.0) * 100.0),
            band_width_pct=_clamp((4.0 / 12.0) * 100.0),
            on_target=spo2_on_target,
        ),
        ClinicalProgressItemOut(
            key="exercise_min",
            label="Daily Exercise",
            subtitle=f"Daily target: {exercise_target_min} min",
            display_value=f"{exercise_min}",
            unit="min",
            status_label=ex_label,
            status_tone=ex_tone,
            progress_pct=_clamp((exercise_min / 110.0) * 100.0),
            band_start_pct=_clamp((75.0 / 110.0) * 100.0),
            band_width_pct=_clamp((35.0 / 110.0) * 100.0),
            on_target=ex_on_target,
        ),
        ClinicalProgressItemOut(
            key="hydration_ml",
            label="Hydration",
            subtitle=hyd_subtitle,
            display_value=f"{hydration_liters:.1f}",
            unit="L",
            status_label=hyd_status,
            status_tone=hyd_tone,
            progress_pct=_clamp((hydration_ml / 3200.0) * 100.0),
            band_start_pct=_clamp((2600.0 / 3200.0) * 100.0),
            band_width_pct=_clamp((600.0 / 3200.0) * 100.0),
            on_target=hyd_on_target,
        ),
        ClinicalProgressItemOut(
            key="calories_kcal",
            label="Caloric Intake",
            subtitle=f"Daily target: {calories_target:,} kcal",
            display_value=f"{calories_kcal:,}",
            unit="kcal",
            status_label="Optimal" if cal_on_target else "Adjust",
            status_tone=cal_tone,
            progress_pct=_clamp((calories_kcal / 3200.0) * 100.0),
            band_start_pct=_clamp(((calories_target - 250.0) / 3200.0) * 100.0),
            band_width_pct=_clamp((500.0 / 3200.0) * 100.0),
            on_target=cal_on_target,
        ),
    ]

    on_target_count = sum(1 for item in vitals_items if item.on_target)
    daily_vitals = DailyVitalsHabitsOut(
        tag_text="CONTINUOUS",
        header_target_badge=f"{on_target_count} / {len(vitals_items)} ON TARGET",
        on_target_count=on_target_count,
        total_count=len(vitals_items),
        items=vitals_items,
    )

    ecg_entry = fallback_metrics.get("ecg_lead_ii_mv")
    stored_samples: list[float] = []
    if ecg_entry:
        raw_samples = ecg_entry["payload"].get("samples_mv")
        if isinstance(raw_samples, list) and len(raw_samples) >= 40:
            stored_samples = [
                round(float(x), 4) for x in raw_samples if isinstance(x, (int, float))
            ]
    samples_mv = (
        stored_samples
        if len(stored_samples) >= 40
        else _generate_lead_ii_waveform(resting_hr, hrv_ms)
    )

    if resting_hr > 100.0:
        rhythm_label = "SINUS TACHYCARDIA"
        rhythm_tone: HudTagTone = "warn" if resting_hr < 115.0 else "critical"
    elif resting_hr < 50.0:
        rhythm_label = "SINUS BRADYCARDIA"
        rhythm_tone = "warn" if resting_hr >= 42.0 else "critical"
    else:
        rhythm_label = "NORMAL SINUS"
        rhythm_tone = "reference"

    live_ecg = LiveEcgOut(
        rhythm_label=rhythm_label,
        rhythm_tone=rhythm_tone,
        lead_label="LEAD II · 25 mm/s",
        resting_hr_bpm=resting_hr,
        hrv_rmssd_ms=hrv_ms,
        body_temp_c=body_temp_c,
        header_summary=f"{round(resting_hr)} BPM · HRV {round(hrv_ms)} MS · {body_temp_c:.1f} °C",
        sample_rate_hz=100,
        samples_mv=samples_mv,
    )

    glucose_val = round(metric_val("blood_glucose_mg_dl", 90.0))
    if 70 <= glucose_val <= 99:
        glucose_status = "Optimal"
        glucose_tone: StatusTone = "nominal"
    elif 65 <= glucose_val <= 125:
        glucose_status = "Borderline"
        glucose_tone = "warn"
    else:
        glucose_status = "Critical"
        glucose_tone = "critical"

    hb_default = 13.8 if sex_code == "F" else 15.1
    hb_val = round(metric_val("hemoglobin_g_dl", hb_default), 1)
    if 12.5 <= hb_val <= 17.0:
        hb_status = "Normal"
        hb_tone: StatusTone = "nominal"
    elif 11.0 <= hb_val <= 18.2:
        hb_status = "Borderline"
        hb_tone = "warn"
    else:
        hb_status = "Critical"
        hb_tone = "critical"

    usg_entry = fallback_metrics.get("urine_specific_gravity")
    if usg_entry and usg_entry["value_num"] is not None:
        usg_val = round(float(usg_entry["value_num"]), 3)
    else:
        usg_val = 1.018 if hydration_ml < 2600 else 1.012

    if 1.005 <= usg_val <= 1.016:
        usg_status = "Optimal"
        usg_tone: StatusTone = "nominal"
        usg_detail = "Weekly strip · Renal hydration balanced"
    elif usg_val <= 1.024:
        usg_status = "Mild Low"
        usg_tone = "warn"
        suggest_ml = max(250, hyd_rem_ml)
        usg_detail = f"Weekly strip · Drink +{suggest_ml} mL today"
    else:
        usg_status = "Concentrated"
        usg_tone = "critical"
        usg_detail = "Weekly strip · Immediate oral electrolyte bolus"

    ausc_row = conn.execute(
        """
        SELECT organ_type, findings_json
        FROM auscultation_recordings
        WHERE crew_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (crew_id,),
    ).fetchone()
    ausc_summary = "S1/S2 clear"
    if ausc_row:
        try:
            findings = json.loads(ausc_row["findings_json"])
            if isinstance(findings, dict) and findings.get("summary"):
                ausc_summary = str(findings["summary"])
        except ValueError:
            pass

    right_payload = (fallback_metrics.get("optic_sheath_right_mm") or {}).get("payload") or {}
    left_payload = (fallback_metrics.get("optic_sheath_left_mm") or {}).get("payload") or {}
    acuity = str(
        right_payload.get("visual_acuity")
        or left_payload.get("visual_acuity")
        or "20/20"
    )

    if max_optic >= 5.8:
        eye_tag = "OD" if optic_right >= optic_left else "OS"
        av_status = f"Critical {eye_tag}"
        av_tone: StatusTone = "critical"
    elif max_optic >= 5.2:
        eye_tag = "OD" if optic_right >= optic_left else "OS"
        av_status = f"Elevated {eye_tag}"
        av_tone = "warn"
    else:
        av_status = "Clear"
        av_tone = "nominal"

    dominant_side = "Right" if optic_right >= optic_left else "Left"
    dominant_mm = optic_right if optic_right >= optic_left else optic_left

    clinical_labs: list[ClinicalLabCardOut] = [
        ClinicalLabCardOut(
            key="blood_glucose",
            label="BLOOD GLUCOSE",
            status_label=glucose_status,
            status_tone=glucose_tone,
            display_value=f"{glucose_val} mg/dL",
            detail="Fasting biweekly check · Range 70–99 mg/dL",
        ),
        ClinicalLabCardOut(
            key="blood_panel",
            label="BLOOD PANEL",
            status_label=hb_status,
            status_tone=hb_tone,
            display_value=f"{hb_val:.1f} g/dL",
            detail="Monthly hemoglobin & electrolytes · Balanced",
        ),
        ClinicalLabCardOut(
            key="urine_specific_gravity",
            label="URINE SPECIFIC GRAVITY",
            status_label=usg_status,
            status_tone=usg_tone,
            display_value=f"{usg_val:.3f} SG",
            detail=usg_detail,
        ),
        ClinicalLabCardOut(
            key="auscultation_vision",
            label="AUSCULTATION & VISION",
            status_label=av_status,
            status_tone=av_tone,
            display_value=f"Clear · {acuity}",
            detail=f"{ausc_summary} · {dominant_side} optic sheath {dominant_mm:.1f} mm",
        ),
    ]

    return CrewProfileOut(
        crew=CrewDemographicsOut(
            id=str(crew_row["id"]),
            code=str(crew_row["code"]),
            full_name=str(crew_row["full_name"]),
            short_name=_short_name(str(crew_row["full_name"])),
            role=crew_role,
            role_badge=ROLE_BADGE_MAP.get(crew_role, crew_role),
            age=int(crew_row["age"]) if crew_row["age"] is not None else None,
            sex=sex_code,
            sex_display=SEX_DISPLAY_MAP.get(sex_code or "", "Unspecified"),
            blood_type=str(crew_row["blood_type"]) if crew_row["blood_type"] else None,
            baseline_height_cm=round(baseline_height, 1),
        ),
        mission=ProfileMissionContextOut(
            mission_code=str(mission_row["mission_code"]) if mission_row else "ARES VII",
            mission_name=(
                str(mission_row["mission_name"])
                if mission_row
                else "Deep Space Transit & Orbital Habitat"
            ),
            current_stage=current_stage,
            selected_stage=selected_stage,
            stage_has_records=stage_has_records,
            mission_day=mission_day,
            mission_day_code=f"DAY {mission_day:03d}",
            elapsed_days_label=f"{mission_day} Days",
            utc_hm=f"{now_dt.strftime('%H:%M')} UTC",
            server_utc=now_utc,
        ),
        stage_comparison=_build_stage_comparison(conn, crew_id),
        biometrics=biometrics,
        biometric_scan=biometric_scan,
        environment_work=environment_work,
        daily_vitals=daily_vitals,
        live_ecg=live_ecg,
        clinical_labs=clinical_labs,
    )
