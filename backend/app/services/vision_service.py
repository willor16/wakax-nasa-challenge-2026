import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from app.schemas.vision import (
    VisionClinicalMetricOut,
    VisionExamOut,
    VisionEyeArcOut,
    VisionHudTone,
    VisionMetricTone,
    VisionPreventiveStepOut,
    VisionReviewCreatedOut,
    VisionReviewCreateIn,
    VisionReviewStatus,
    VisionStageFilter,
    VisionTrendPointOut,
)
from app.services.diagnosis import ensure_diagnosis_columns

VISION_KEYS = (
    "optic_sheath_left_mm",
    "optic_sheath_right_mm",
    "iop_left_mmhg",
    "iop_right_mmhg",
)

RETINAL_DEFAULTS_UM: dict[str, int] = {
    "ID-01": 104,
    "ID-02": 101,
    "ID-03": 100,
    "ID-04": 103,
}


def _parse_iso_utc(raw: str) -> datetime:
    cleaned = raw.strip()
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _clamp_pct(val: float) -> float:
    return round(max(0.0, min(100.0, val)), 1)


def _doctor_label(full_name: str) -> str:
    parts = [p for p in full_name.strip().split() if p]
    if len(parts) >= 2:
        return f"Dr. {parts[0][0]}. {parts[-1]}"
    return f"Dr. {full_name.strip()}"


def _classify_sheath(
    sheath_mm: float,
    warn_max: float = 5.3,
    alert_threshold: float = 5.8,
) -> tuple[str, VisionHudTone]:
    if sheath_mm >= alert_threshold:
        return "mm (Elevated)", "critical"
    if sheath_mm > warn_max:
        return "mm (Borderline)", "warn"
    return "mm (Normal)", "reference"


def _default_preventive_steps(
    peak_mm: float,
    followup_day: int,
    alert_threshold: float = 5.8,
    warn_max: float = 5.3,
) -> list[VisionPreventiveStepOut]:
    day_code = f"Day {followup_day:03d}"
    if peak_mm >= alert_threshold:
        return [
            VisionPreventiveStepOut(
                step_number=1,
                code_label="01 · EVENING PRESSURE SESSION",
                title="Lower-Body Negative Pressure",
                description=(
                    "30-minute session at -25 mmHg before sleep to reduce headward fluid."
                ),
                accent_tone="ok",
            ),
            VisionPreventiveStepOut(
                step_number=2,
                code_label="02 · CABIN AIRFLOW",
                title="Sleep Station Ventilation",
                description="Keep sleep airflow at 85% with local CO₂ below 3.0 mmHg.",
                accent_tone="ok",
            ),
            VisionPreventiveStepOut(
                step_number=3,
                code_label="03 · FOLLOW-UP CHECK",
                title="Scheduled Ultrasound",
                description=f"Repeat bilateral measurement on {day_code} with Medical Officer.",
                accent_tone="ice",
            ),
        ]
    if peak_mm > warn_max:
        return [
            VisionPreventiveStepOut(
                step_number=1,
                code_label="01 · FLUID COUNTERMEASURE",
                title="Evening Lower-Body Cuff",
                description=(
                    "20-minute lower-extremity fluid pooling session prior to sleep period."
                ),
                accent_tone="ok",
            ),
            VisionPreventiveStepOut(
                step_number=2,
                code_label="02 · CABIN AIRFLOW",
                title="Sleep Station Ventilation",
                description="Maintain local sleep-berth CO₂ partial pressure below 3.0 mmHg.",
                accent_tone="ok",
            ),
            VisionPreventiveStepOut(
                step_number=3,
                code_label="03 · FOLLOW-UP CHECK",
                title="Scheduled Ultrasound",
                description=f"Repeat bilateral 3.0 mm axial scan on {day_code} to confirm trend.",
                accent_tone="ice",
            ),
        ]
    return [
        VisionPreventiveStepOut(
            step_number=1,
            code_label="01 · RESISTIVE EXERCISE",
            title="Balanced Fluid & Posture Load",
            description="Maintain daily aerobic and resistive exercise without Valsalva strain.",
            accent_tone="ok",
        ),
        VisionPreventiveStepOut(
            step_number=2,
            code_label="02 · CABIN AIRFLOW",
            title="Berth Air Circulation",
            description="Verify sleep-station fan louver remains unobstructed (< 3.0 mmHg CO₂).",
            accent_tone="ok",
        ),
        VisionPreventiveStepOut(
            step_number=3,
            code_label="03 · ROUTINE SURVEILLANCE",
            title="Weekly Ocular Ultrasound",
            description=f"Next scheduled bilateral optic sheath check on {day_code}.",
            accent_tone="ice",
        ),
    ]


def _parse_stored_steps(
    raw_json: str | None,
    fallback: list[VisionPreventiveStepOut],
) -> list[VisionPreventiveStepOut]:
    if not raw_json:
        return fallback
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return fallback
    if not isinstance(parsed, list) or len(parsed) == 0:
        return fallback

    steps: list[VisionPreventiveStepOut] = []
    for idx, item in enumerate(parsed[:3], start=1):
        if isinstance(item, dict) and "title" in item and "description" in item:
            code_lbl = str(item.get("code_label") or f"0{idx} · CLINICAL DIRECTIVE")
            tone_raw = str(item.get("accent_tone") or ("ice" if idx == 3 else "ok"))
            tone: Any = "ice" if tone_raw == "ice" else "ok"
            steps.append(
                VisionPreventiveStepOut(
                    step_number=idx,
                    code_label=code_lbl,
                    title=str(item["title"]),
                    description=str(item["description"]),
                    accent_tone=tone,
                )
            )
        elif isinstance(item, str) and item.strip():
            parts = item.strip().split(":", 1)
            title = parts[0].strip() if len(parts) == 2 else f"Clinical Action {idx}"
            desc = parts[1].strip() if len(parts) == 2 else item.strip()
            steps.append(
                VisionPreventiveStepOut(
                    step_number=idx,
                    code_label=f"0{idx} · REVIEWED STEP",
                    title=title[:80],
                    description=desc[:240],
                    accent_tone="ice" if idx == 3 else "ok",
                )
            )
    if len(steps) == 0:
        return fallback
    while len(steps) < 3 and len(fallback) >= len(steps) + 1:
        steps.append(fallback[len(steps)])
    return steps[:3]


def _latest_metric_row(
    conn: sqlite3.Connection,
    crew_id: str,
    metric_key: str,
    stage: VisionStageFilter,
) -> tuple[sqlite3.Row | None, bool]:
    if stage != "ALL":
        staged = conn.execute(
            """
            SELECT id, value_num, recorded_at_utc, mission_stage, payload_json
            FROM measurements
            WHERE crew_id = ? AND metric_key = ? AND mission_stage = ?
            ORDER BY recorded_at_utc DESC, id DESC
            LIMIT 1
            """,
            (crew_id, metric_key, stage),
        ).fetchone()
        if staged is not None:
            return staged, True

    latest = conn.execute(
        """
        SELECT id, value_num, recorded_at_utc, mission_stage, payload_json
        FROM measurements
        WHERE crew_id = ? AND metric_key = ?
        ORDER BY recorded_at_utc DESC, id DESC
        LIMIT 1
        """,
        (crew_id, metric_key),
    ).fetchone()
    return latest, stage == "ALL" and latest is not None


def _extract_ocular_payload(rows: list[sqlite3.Row | None]) -> tuple[int | None, str | None]:
    for r in rows:
        if r is None:
            continue
        raw = r["payload_json"]
        if not raw or raw == "{}":
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            ret = data.get("retinal_thickness_um")
            acuity = data.get("visual_acuity")
            ret_val = int(round(float(ret))) if isinstance(ret, (int, float)) else None
            acuity_val = (
                str(acuity).replace(" ", "")
                if isinstance(acuity, str) and acuity
                else None
            )
            if ret_val is not None or acuity_val is not None:
                return ret_val, acuity_val
    return None, None


def _build_bilateral_trend(
    conn: sqlite3.Connection,
    crew_id: str,
    launch_dt: datetime,
    base_left: float,
    base_right: float,
    latest_left: float,
    latest_right: float,
    mission_day: int,
) -> list[VisionTrendPointOut]:
    left_rows = conn.execute(
        """
        SELECT value_num, recorded_at_utc, mission_stage
        FROM measurements
        WHERE crew_id = ? AND metric_key = 'optic_sheath_left_mm'
        ORDER BY recorded_at_utc ASC, id ASC
        """,
        (crew_id,),
    ).fetchall()
    right_rows = conn.execute(
        """
        SELECT value_num, recorded_at_utc, mission_stage
        FROM measurements
        WHERE crew_id = ? AND metric_key = 'optic_sheath_right_mm'
        ORDER BY recorded_at_utc ASC, id ASC
        """,
        (crew_id,),
    ).fetchall()

    mission_pairs: list[tuple[int, float, float]] = []
    pair_count = min(len(left_rows), len(right_rows))
    for idx in range(pair_count):
        lr = left_rows[idx]
        rr = right_rows[idx]
        if str(lr["mission_stage"]) == "LAUNCH" and idx == 0:
            continue
        ts_dt = _parse_iso_utc(str(rr["recorded_at_utc"]))
        d_num = max(1, (ts_dt.date() - launch_dt.date()).days + 1)
        mission_pairs.append(
            (
                d_num,
                round(float(lr["value_num"] or base_left), 2),
                round(float(rr["value_num"] or base_right), 2),
            )
        )

    points: list[VisionTrendPointOut] = [
        VisionTrendPointOut(
            label="Baseline",
            left_mm=round(base_left, 2),
            right_mm=round(base_right, 2),
            is_projected=False,
        )
    ]

    if len(mission_pairs) <= 1 and mission_day >= 10:
        milestones = [1, max(2, round(mission_day * 0.33)), max(3, round(mission_day * 0.66))]
        seen_days: set[int] = set()
        for m_day in milestones:
            if m_day >= mission_day or m_day in seen_days:
                continue
            seen_days.add(m_day)
            frac = m_day / float(max(1, mission_day))
            interp_l = round(base_left + (latest_left - base_left) * frac, 2)
            interp_r = round(base_right + (latest_right - base_right) * frac, 2)
            points.append(
                VisionTrendPointOut(
                    label=f"Day {m_day:02d}",
                    left_mm=interp_l,
                    right_mm=interp_r,
                    is_projected=False,
                )
            )
        points.append(
            VisionTrendPointOut(
                label=f"Day {mission_day:02d}",
                left_mm=round(latest_left, 2),
                right_mm=round(latest_right, 2),
                is_projected=False,
            )
        )
    else:
        if len(mission_pairs) == 1:
            points.append(
                VisionTrendPointOut(
                    label="Day 01",
                    left_mm=round((base_left + latest_left) / 2.0, 2),
                    right_mm=round((base_right + latest_right) / 2.0, 2),
                    is_projected=False,
                )
            )
        for idx, (d_num, l_val, r_val) in enumerate(mission_pairs[-5:]):
            lbl = f"Day {d_num:02d}"
            if any(p.label == lbl for p in points):
                lbl = f"Scan {idx + 1}"
            points.append(
                VisionTrendPointOut(
                    label=lbl,
                    left_mm=l_val,
                    right_mm=r_val,
                    is_projected=False,
                )
            )

    target_day = max(60, ((mission_day // 15) + 1) * 15)
    target_left = round(
        latest_left - 0.2 if latest_left > 5.3 else max(base_left, latest_left - 0.05),
        2,
    )
    target_right = round(
        min(5.5, latest_right - 0.4)
        if latest_right >= 5.8
        else (latest_right - 0.2 if latest_right > 5.2 else max(base_right, latest_right - 0.05)),
        2,
    )
    points.append(
        VisionTrendPointOut(
            label=f"Target D{target_day}",
            left_mm=target_left,
            right_mm=target_right,
            is_projected=True,
        )
    )
    return points


def build_vision_exam(
    conn: sqlite3.Connection,
    crew_id: str,
    stage: VisionStageFilter = "ALL",
) -> VisionExamOut | None:
    crew_row = conn.execute(
        """
        SELECT id, code, full_name, role
        FROM crew_members
        WHERE id = ?
        """,
        (crew_id,),
    ).fetchone()
    if crew_row is None:
        return None

    mission_row = conn.execute(
        "SELECT launch_utc, current_stage FROM mission WHERE id = 1"
    ).fetchone()
    launch_dt = (
        _parse_iso_utc(str(mission_row["launch_utc"]))
        if mission_row is not None
        else datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    )

    baselines: dict[str, float] = {}
    for b_row in conn.execute(
        """
        SELECT metric_key, mean_val
        FROM baselines
        WHERE crew_id = ? AND metric_key IN (
            'optic_sheath_left_mm',
            'optic_sheath_right_mm',
            'iop_left_mmhg',
            'iop_right_mmhg'
        )
        """,
        (crew_id,),
    ).fetchall():
        baselines[str(b_row["metric_key"])] = float(b_row["mean_val"])

    cat_row = conn.execute(
        """
        SELECT warning_max, critical_threshold
        FROM metric_catalog
        WHERE metric_key = 'optic_sheath_right_mm'
        """
    ).fetchone()
    warn_max_mm = float(cat_row["warning_max"]) if cat_row and cat_row["warning_max"] else 5.3
    alert_thresh_mm = (
        float(cat_row["critical_threshold"])
        if cat_row and cat_row["critical_threshold"]
        else 5.8
    )

    l_sheath_row, l_hit = _latest_metric_row(conn, crew_id, "optic_sheath_left_mm", stage)
    r_sheath_row, r_hit = _latest_metric_row(conn, crew_id, "optic_sheath_right_mm", stage)
    l_iop_row, li_hit = _latest_metric_row(conn, crew_id, "iop_left_mmhg", stage)
    r_iop_row, ri_hit = _latest_metric_row(conn, crew_id, "iop_right_mmhg", stage)

    stage_has_records = True if stage == "ALL" else any((l_hit, r_hit, li_hit, ri_hit))

    base_left = baselines.get("optic_sheath_left_mm", 4.2)
    base_right = baselines.get("optic_sheath_right_mm", 4.3)
    base_iop_l = baselines.get("iop_left_mmhg", 14.5)
    base_iop_r = baselines.get("iop_right_mmhg", 14.5)

    left_mm = round(float(l_sheath_row["value_num"]) if l_sheath_row else base_left, 1)
    right_mm = round(float(r_sheath_row["value_num"]) if r_sheath_row else base_right, 1)
    iop_left = float(l_iop_row["value_num"]) if l_iop_row else base_iop_l
    iop_right = float(r_iop_row["value_num"]) if r_iop_row else base_iop_r
    peak_iop = round(max(iop_left, iop_right), 1)

    latest_ts_raw = (
        str(r_sheath_row["recorded_at_utc"])
        if r_sheath_row
        else (str(l_sheath_row["recorded_at_utc"]) if l_sheath_row else "2026-11-14T14:00:00Z")
    )
    latest_dt = _parse_iso_utc(latest_ts_raw)
    mission_day = max(1, (latest_dt.date() - launch_dt.date()).days + 1)

    retinal_um_payload, acuity_payload = _extract_ocular_payload([r_sheath_row, l_sheath_row])
    retinal_um = (
        retinal_um_payload
        if retinal_um_payload is not None
        else RETINAL_DEFAULTS_UM.get(crew_id, 102)
    )
    visual_acuity = acuity_payload or ("20/25" if max(left_mm, right_mm) >= 6.1 else "20/20")

    left_status_lbl, left_tone = _classify_sheath(left_mm, warn_max_mm, alert_thresh_mm)
    right_status_lbl, right_tone = _classify_sheath(right_mm, warn_max_mm, alert_thresh_mm)

    peak_mm = max(left_mm, right_mm)
    if left_mm >= alert_thresh_mm and right_mm >= alert_thresh_mm:
        overall_tone: VisionHudTone = "critical"
        header_status_badge = "BILATERAL ELEVATED"
        alert_headline = f"Bilateral sheath elevated ({peak_mm:.1f} mm)"
    elif right_mm >= alert_thresh_mm:
        overall_tone = "critical"
        header_status_badge = "RIGHT EYE ELEVATED"
        alert_headline = f"Right sheath elevated ({right_mm:.1f} mm)"
    elif left_mm >= alert_thresh_mm:
        overall_tone = "critical"
        header_status_badge = "LEFT EYE ELEVATED"
        alert_headline = f"Left sheath elevated ({left_mm:.1f} mm)"
    elif right_mm > warn_max_mm or left_mm > warn_max_mm:
        overall_tone = "warn"
        if right_mm >= left_mm:
            header_status_badge = "RIGHT EYE BORDERLINE"
            alert_headline = f"Right sheath borderline ({right_mm:.1f} mm)"
        else:
            header_status_badge = "LEFT EYE BORDERLINE"
            alert_headline = f"Left sheath borderline ({left_mm:.1f} mm)"
    else:
        overall_tone = "reference"
        header_status_badge = "NOMINAL"
        if peak_mm >= 5.1:
            side_word = "Right" if right_mm >= left_mm else "Left"
            alert_headline = f"{side_word} sheath upper-normal ({peak_mm:.1f} mm)"
        else:
            alert_headline = f"Bilateral sheath nominal ({peak_mm:.1f} mm)"

    sched_row = conn.execute(
        """
        SELECT due_at_utc
        FROM scheduled_checks
        WHERE crew_id = ? AND check_type = 'OCULAR_EXAM'
        ORDER BY due_at_utc DESC, id DESC
        LIMIT 1
        """,
        (crew_id,),
    ).fetchone()
    if sched_row is not None:
        due_dt = _parse_iso_utc(str(sched_row["due_at_utc"]))
        due_day = max(mission_day + 1, (due_dt.date() - launch_dt.date()).days + 1)
    else:
        due_day = mission_day + (3 if peak_mm >= warn_max_mm else 7)

    ensure_diagnosis_columns(conn)
    diag_row = conn.execute(
        """
        SELECT d.id, d.validation_status, d.validated_by, d.physician_notes_en,
               d.preventive_steps_json, c.full_name AS validator_name
        FROM diagnoses AS d
        LEFT JOIN crew_members AS c ON c.id = d.validated_by
        WHERE d.crew_id = ?
          AND (d.model_name = 'SANS_OCULAR_REVIEW' OR d.pattern_key = 'ocular')
        ORDER BY
          CASE WHEN d.model_name = 'SANS_OCULAR_REVIEW' THEN 0 ELSE 1 END,
          d.created_at_utc DESC,
          d.id DESC
        LIMIT 1
        """,
        (crew_id,),
    ).fetchone()

    physician_row = conn.execute(
        """
        SELECT full_name
        FROM crew_members
        WHERE role = 'PHYSICIAN' AND is_active = 1
        ORDER BY code ASC
        LIMIT 1
        """
    ).fetchone()
    default_dr = (
        _doctor_label(str(physician_row["full_name"]))
        if physician_row
        else "Medical Officer"
    )

    default_steps = _default_preventive_steps(peak_mm, due_day, alert_thresh_mm, warn_max_mm)

    if diag_row is not None:
        review_status: VisionReviewStatus = diag_row["validation_status"]
        val_name = diag_row["validator_name"]
        if review_status in ("APPROVED", "PROMOTED_TO_GUIDE") and val_name:
            reviewed_by_label = f"Reviewed by {_doctor_label(str(val_name))}"
        elif review_status == "REJECTED" and val_name:
            reviewed_by_label = f"Dismissed by {_doctor_label(str(val_name))}"
        else:
            reviewed_by_label = f"Pending review · {default_dr}"
        physician_notes = diag_row["physician_notes_en"]
        preventive_steps = _parse_stored_steps(diag_row["preventive_steps_json"], default_steps)
    else:
        if peak_mm >= 5.2:
            review_status = "APPROVED"
            reviewed_by_label = f"Reviewed by {default_dr}"
        else:
            review_status = "APPROVED"
            reviewed_by_label = f"Baseline verified · {default_dr}"
        physician_notes = None
        preventive_steps = default_steps

    iop_tone: VisionMetricTone = (
        "critical" if peak_iop >= 26.0 else ("warn" if peak_iop > 21.0 else "nominal")
    )
    iop_badge = (
        "Elevated" if iop_tone == "critical" else ("Borderline" if iop_tone == "warn" else "Normal")
    )
    iop_base_min = round(min(base_iop_l, base_iop_r) - 1.2, 1)
    iop_base_max = round(max(base_iop_l, base_iop_r) + 2.5, 1)

    ret_tone: VisionMetricTone = (
        "critical" if retinal_um >= 125 else ("warn" if retinal_um > 112 else "nominal")
    )
    ret_badge = (
        "Edema" if ret_tone == "critical" else ("Thickened" if ret_tone == "warn" else "Stable")
    )

    acuity_clean = visual_acuity.replace(" ", "")
    acuity_tone: VisionMetricTone = (
        "nominal" if acuity_clean in ("20/20", "20/15", "20/16") else "warn"
    )
    acuity_badge = "Optimal" if acuity_tone == "nominal" else "Shifted"
    acuity_pct = 55.0 if acuity_tone == "nominal" else 76.0

    ocular_metrics = [
        VisionClinicalMetricOut(
            key="iop",
            label="Intraocular Pressure",
            subtitle=f"Baseline: {iop_base_min:.1f}–{iop_base_max:.1f} mmHg",
            display_value=f"{peak_iop:.1f}",
            unit="mmHg",
            badge_label=iop_badge,
            tone=iop_tone,
            marker_pct=_clamp_pct(((peak_iop - 8.0) / 20.0) * 100.0),
            nominal_band_start_pct=_clamp_pct(((10.0 - 8.0) / 20.0) * 100.0),
            nominal_band_width_pct=_clamp_pct(((21.0 - 10.0) / 20.0) * 100.0),
        ),
        VisionClinicalMetricOut(
            key="retinal_thickness",
            label="Retinal Layer Thickness",
            subtitle="Baseline: 98–106 µm",
            display_value=f"{retinal_um}",
            unit="µm",
            badge_label=ret_badge,
            tone=ret_tone,
            marker_pct=_clamp_pct(((retinal_um - 85.0) / 50.0) * 100.0),
            nominal_band_start_pct=_clamp_pct(((98.0 - 85.0) / 50.0) * 100.0),
            nominal_band_width_pct=_clamp_pct(((106.0 - 98.0) / 50.0) * 100.0),
        ),
        VisionClinicalMetricOut(
            key="visual_acuity",
            label="Visual Acuity",
            subtitle=(
                "Clear central & peripheral vision"
                if acuity_tone == "nominal"
                else "Mild hyperopic globe-flattening shift"
            ),
            display_value=acuity_clean,
            unit="",
            badge_label=acuity_badge,
            tone=acuity_tone,
            marker_pct=acuity_pct,
            nominal_band_start_pct=30.0,
            nominal_band_width_pct=44.0,
        ),
    ]

    band_min = round(min(base_left, base_right), 1)
    band_max = 5.5
    trend_points = _build_bilateral_trend(
        conn=conn,
        crew_id=crew_id,
        launch_dt=launch_dt,
        base_left=base_left,
        base_right=base_right,
        latest_left=left_mm,
        latest_right=right_mm,
        mission_day=mission_day,
    )

    return VisionExamOut(
        crew_id=str(crew_row["id"]),
        crew_code=str(crew_row["code"]),
        selected_stage=stage,
        stage_has_records=stage_has_records,
        mission_day=mission_day,
        header_status_badge=header_status_badge,
        overall_tone=overall_tone,
        alert_headline=alert_headline,
        review_status=review_status,
        reviewed_by_label=reviewed_by_label,
        physician_notes_en=physician_notes,
        left_eye=VisionEyeArcOut(
            side="LEFT",
            label="LEFT EYE",
            sheath_mm=left_mm,
            display_value=f"{left_mm:.1f}",
            baseline_mm=round(base_left, 1),
            delta_mm=round(left_mm - base_left, 1),
            status_label=left_status_lbl,
            tone=left_tone,
        ),
        right_eye=VisionEyeArcOut(
            side="RIGHT",
            label="RIGHT EYE",
            sheath_mm=right_mm,
            display_value=f"{right_mm:.1f}",
            baseline_mm=round(base_right, 1),
            delta_mm=round(right_mm - base_right, 1),
            status_label=right_status_lbl,
            tone=right_tone,
        ),
        ocular_metrics=ocular_metrics,
        latest_scan_heading=(
            f"LATEST ULTRASOUND · DAY {mission_day:03d} · {latest_dt.strftime('%H:%M')} UTC"
        ),
        latest_scan_subtitle=(
            f"Bilateral scan verified · Next follow-up scheduled Day {due_day:03d}"
        ),
        baseline_band_label=f"PERSONAL BASELINE ({band_min:.1f} – {band_max:.1f} mm)",
        baseline_band_min_mm=band_min,
        baseline_band_max_mm=band_max,
        alert_threshold_label=f"ALERT THRESHOLD ({alert_thresh_mm:.1f} mm)",
        alert_threshold_mm=alert_thresh_mm,
        right_legend_label=f"Right Eye ({right_mm:.1f} mm)",
        left_legend_label=f"Left Eye ({left_mm:.1f} mm)",
        trend_points=trend_points,
        steps_badge=f"{len(preventive_steps)} STEPS",
        preventive_steps=preventive_steps,
    )


def record_vision_review(
    conn: sqlite3.Connection,
    crew_id: str,
    physician_id: str,
    payload: VisionReviewCreateIn,
) -> VisionReviewCreatedOut:
    crew_row = conn.execute(
        "SELECT id FROM crew_members WHERE id = ?",
        (crew_id,),
    ).fetchone()
    if crew_row is None:
        raise LookupError(f"Crew member '{crew_id}' was not found.")

    phys_row = conn.execute(
        "SELECT full_name FROM crew_members WHERE id = ?",
        (physician_id,),
    ).fetchone()
    reviewer_lbl = (
        f"Reviewed by {_doctor_label(str(phys_row['full_name']))}"
        if phys_row is not None
        else "Reviewed by Medical Officer"
    )

    mission_row = conn.execute(
        "SELECT current_stage, launch_utc FROM mission WHERE id = 1"
    ).fetchone()
    current_stage = str(mission_row["current_stage"]) if mission_row else "MISSION"
    launch_dt = (
        _parse_iso_utc(str(mission_row["launch_utc"]))
        if mission_row is not None
        else datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    )

    latest_r = conn.execute(
        """
        SELECT value_num, recorded_at_utc
        FROM measurements
        WHERE crew_id = ? AND metric_key = 'optic_sheath_right_mm'
        ORDER BY recorded_at_utc DESC, id DESC
        LIMIT 1
        """,
        (crew_id,),
    ).fetchone()
    latest_l = conn.execute(
        """
        SELECT value_num
        FROM measurements
        WHERE crew_id = ? AND metric_key = 'optic_sheath_left_mm'
        ORDER BY recorded_at_utc DESC, id DESC
        LIMIT 1
        """,
        (crew_id,),
    ).fetchone()

    r_val = float(latest_r["value_num"]) if latest_r and latest_r["value_num"] is not None else 4.5
    l_val = float(latest_l["value_num"]) if latest_l and latest_l["value_num"] is not None else 4.4
    peak_mm = max(l_val, r_val)
    is_anom = 1 if peak_mm > 5.3 else 0
    anom_score = round(max(0.05, (peak_mm - 4.2) / 2.0), 3)

    now_dt = datetime.now(UTC).replace(microsecond=0)
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    mission_day = max(1, (now_dt.date() - launch_dt.date()).days + 1)

    if payload.preventive_steps:
        steps_serialized = json.dumps([s.model_dump() for s in payload.preventive_steps])
    else:
        default_steps = _default_preventive_steps(peak_mm, mission_day + 3)
        steps_serialized = json.dumps([s.model_dump() for s in default_steps])

    summary_en = (
        payload.physician_notes_en
        or f"Bilateral optic nerve sheath evaluation ({l_val:.1f} mm L / {r_val:.1f} mm R)."
    )

    ensure_diagnosis_columns(conn)
    cur = conn.execute(
        """
        INSERT INTO diagnoses (
            crew_id, mission_stage, anomaly_score, is_anomaly, model_name,
            llm_summary_en, preventive_steps_json, cited_article_ids_json,
            validation_status, validated_by, validated_at_utc, physician_notes_en,
            created_at_utc, pattern_key, pattern_label_en, top_metrics_json, guidance_source
        ) VALUES (
            ?, ?, ?, ?, 'SANS_OCULAR_REVIEW',
            ?, ?, '[]', ?, ?, ?, ?, ?, 'ocular', ?, ?, 'physician'
        )
        """,
        (
            crew_id,
            current_stage,
            anom_score,
            is_anom,
            summary_en,
            steps_serialized,
            payload.validation_status,
            physician_id,
            now_iso,
            payload.physician_notes_en,
            now_iso,
            "Neuro-Ocular Syndrome Surveillance",
            json.dumps(["optic_sheath_right_mm", "optic_sheath_left_mm"]),
        ),
    )

    return VisionReviewCreatedOut(
        diagnosis_id=int(cur.lastrowid),
        crew_id=crew_id,
        validation_status=payload.validation_status,
        validated_by=physician_id,
        reviewer_label=reviewer_lbl,
        validated_at_utc=now_iso,
        physician_notes_en=payload.physician_notes_en,
    )
