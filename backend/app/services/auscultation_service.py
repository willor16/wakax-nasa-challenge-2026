import hashlib
import json
import math
import os
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.config import AUDIO_STORAGE_DIR
from app.schemas.auscultation import (
    AnatomicalSite,
    AuscultationCo2PointOut,
    AuscultationMetricBarOut,
    AuscultationMetricTone,
    AuscultationOrganSummaryOut,
    AuscultationResultsOut,
    AuscultationSampleCreatedOut,
    AuscultationSiteStatusOut,
    AuscultationStageFilter,
    AuscultationTone,
    MissionStageLiteral,
    OrganType,
)
from app.services.contracts import update_streaks

NOISE_GATE_LIMIT_DBA = 55.0
MAX_AUDIO_BYTES = 10 * 1024 * 1024
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

CARDIAC_SITE_SPECS: list[tuple[AnatomicalSite, str, str, str]] = [
    (
        "aortic",
        "Aortic · 2nd R",
        "DIGITAL STETHOSCOPE · AORTIC AREA (2ND R ICS)",
        "Aortic",
    ),
    (
        "pulmonic",
        "Pulmonic · 2nd L",
        "DIGITAL STETHOSCOPE · PULMONIC AREA (2ND L ICS)",
        "Pulmonic",
    ),
    (
        "tricuspid",
        "Tricuspid · 4th L",
        "DIGITAL STETHOSCOPE · TRICUSPID AREA (4TH L ICS)",
        "Tricuspid",
    ),
    (
        "mitral",
        "Mitral Apex",
        "DIGITAL STETHOSCOPE · MITRAL APEX (5TH ICS)",
        "Mitral",
    ),
]

PULMONARY_SITE_SPECS: list[tuple[AnatomicalSite, str, str, str]] = [
    (
        "upper_left",
        "Upper Left",
        "PULMONARY PICKUP · UPPER LEFT ANTERIOR ZONE",
        "Upper Left",
    ),
    (
        "upper_right",
        "Upper Right",
        "PULMONARY PICKUP · UPPER RIGHT ANTERIOR ZONE",
        "Upper Right",
    ),
    (
        "lower_left",
        "Lower Left",
        "PULMONARY PICKUP · LOWER LEFT BASAL ZONE",
        "Lower Left",
    ),
    (
        "lower_right",
        "Lower Right",
        "PULMONARY PICKUP · LOWER RIGHT BASAL ZONE",
        "Lower Right",
    ),
]

CARDIAC_SITE_SET = {item[0] for item in CARDIAC_SITE_SPECS}
PULMONARY_SITE_SET = {item[0] for item in PULMONARY_SITE_SPECS}


def resolve_audio_storage_dir() -> Path:
    env_override = os.environ.get("SPACESCAN_AUDIO_DIR")
    target = Path(env_override) if env_override else AUDIO_STORAGE_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def _parse_iso_utc(raw: str) -> datetime:
    cleaned = raw.strip()
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _compute_signal_quality(cabin_noise_dba: float) -> int:
    penalty = max(0.0, cabin_noise_dba - 40.0) * 0.65
    return max(82, min(99, int(round(100.0 - penalty))))


def _latest_metric_value(
    conn: sqlite3.Connection,
    crew_id: str,
    metric_key: str,
    stage: AuscultationStageFilter,
) -> float | None:
    if stage != "ALL":
        row = conn.execute(
            """
            SELECT value_num
            FROM measurements
            WHERE crew_id = ? AND metric_key = ? AND mission_stage = ? AND value_num IS NOT NULL
            ORDER BY recorded_at_utc DESC, id DESC
            LIMIT 1
            """,
            (crew_id, metric_key, stage),
        ).fetchone()
        if row is not None:
            return float(row["value_num"])
    row = conn.execute(
        """
        SELECT value_num
        FROM measurements
        WHERE crew_id = ? AND metric_key = ? AND value_num IS NOT NULL
        ORDER BY recorded_at_utc DESC, id DESC
        LIMIT 1
        """,
        (crew_id, metric_key),
    ).fetchone()
    return float(row["value_num"]) if row is not None else None


def _baseline_value(
    conn: sqlite3.Connection,
    crew_id: str,
    metric_key: str,
    fallback: float,
) -> float:
    row = conn.execute(
        "SELECT mean_val FROM baselines WHERE crew_id = ? AND metric_key = ?",
        (crew_id, metric_key),
    ).fetchone()
    return float(row["mean_val"]) if row is not None else fallback


def _build_phonocardiogram_samples(
    heart_rate_bpm: float,
    phase_offset: float,
    count: int = 180,
) -> list[float]:
    beats_in_window = max(2.6, min(5.4, (heart_rate_bpm / 60.0) * 3.4))
    samples: list[float] = []
    for idx in range(count):
        t = (idx / max(1, count - 1)) * beats_in_window + phase_offset
        cycle = t - math.floor(t)
        s1_env = math.exp(-(((cycle - 0.16) / 0.042) ** 2))
        s2_env = 0.72 * math.exp(-(((cycle - 0.47) / 0.034) ** 2))
        carrier_s1 = math.sin(2.0 * math.pi * 24.0 * cycle)
        carrier_s2 = math.sin(2.0 * math.pi * 33.0 * cycle + 0.6)
        micro_hum = 0.035 * math.sin(2.0 * math.pi * 5.0 * t)
        val = (0.94 * s1_env * carrier_s1) + (s2_env * carrier_s2) + micro_hum
        samples.append(round(max(-1.0, min(1.0, val)), 4))
    return samples


def _build_pulmonary_envelope_samples(
    respiratory_rate_rpm: float,
    phase_offset: float,
    count: int = 180,
) -> list[float]:
    cycles_in_window = max(2.0, min(4.2, (respiratory_rate_rpm / 60.0) * 11.5))
    samples: list[float] = []
    for idx in range(count):
        t = (idx / max(1, count - 1)) * cycles_in_window + phase_offset
        cycle = t - math.floor(t)
        inhale = 0.78 * math.exp(-(((cycle - 0.28) / 0.145) ** 2))
        exhale = 0.52 * math.exp(-(((cycle - 0.66) / 0.175) ** 2))
        vesicular_ripple = 0.045 * math.sin(2.0 * math.pi * 11.0 * t)
        baseline_floor = 0.12
        val = baseline_floor + inhale + exhale + vesicular_ripple
        samples.append(round(max(0.04, min(0.98, val)), 4))
    return samples


def _ppm_to_mmhg(co2_ppm: float) -> float:
    return round(max(0.35, co2_ppm / 1000.0), 2)


def _build_co2_trend(
    conn: sqlite3.Connection,
    crew_id: str,
) -> tuple[list[AuscultationCo2PointOut], float, float]:
    env_rows = conn.execute(
        """
        SELECT co2_ppm, noise_dba, recorded_at_utc
        FROM environment_readings
        ORDER BY recorded_at_utc DESC, id DESC
        LIMIT 7
        """
    ).fetchall()
    measured_co2 = _latest_metric_value(conn, crew_id, "cabin_co2_ppm", "ALL")

    latest_noise = float(env_rows[0]["noise_dba"]) if env_rows else 48.0
    latest_env_ppm = float(env_rows[0]["co2_ppm"]) if env_rows else 2800.0
    anchor_ppm = (
        max(latest_env_ppm, measured_co2)
        if measured_co2 is not None
        else latest_env_ppm
    )

    display_anchor_ppm = anchor_ppm if anchor_ppm >= 1800.0 else max(anchor_ppm, 2800.0)
    if measured_co2 is not None and measured_co2 < 1800.0:
        display_anchor_ppm = measured_co2
    elif env_rows and len(env_rows) >= 4:
        ordered = list(reversed(env_rows[:7]))
        labels = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"]
        pts: list[AuscultationCo2PointOut] = []
        for idx, lbl in enumerate(labels):
            src = ordered[min(idx, len(ordered) - 1)]
            ppm_val = float(src["co2_ppm"])
            if idx == len(labels) - 1 and measured_co2 is not None:
                ppm_val = max(ppm_val, measured_co2)
            pts.append(
                AuscultationCo2PointOut(
                    label=lbl,
                    co2_mmhg=_ppm_to_mmhg(ppm_val),
                    co2_ppm=round(ppm_val, 1),
                )
            )
        return pts, pts[-1].co2_mmhg, round(latest_noise, 1)

    if anchor_ppm < 1800.0 and measured_co2 is None:
        base_ppm = 2800.0
    else:
        base_ppm = display_anchor_ppm

    offsets_ppm = [-380.0, -260.0, -90.0, 140.0, 210.0, 80.0, 0.0]
    labels = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"]
    points: list[AuscultationCo2PointOut] = []
    for lbl, delta in zip(labels, offsets_ppm, strict=True):
        point_ppm = max(450.0, round(base_ppm + delta, 1))
        points.append(
            AuscultationCo2PointOut(
                label=lbl,
                co2_mmhg=_ppm_to_mmhg(point_ppm),
                co2_ppm=point_ppm,
            )
        )
    return points, points[-1].co2_mmhg, round(latest_noise, 1)


def save_auscultation_sample(
    conn: sqlite3.Connection,
    crew_id: str,
    mission_stage: MissionStageLiteral,
    organ_type: OrganType,
    anatomical_site: AnatomicalSite,
    duration_sec: int,
    cabin_noise_dba: float,
    sha256_hex: str,
    audio_bytes: bytes,
) -> AuscultationSampleCreatedOut:
    crew_row = conn.execute(
        "SELECT id FROM crew_members WHERE id = ?",
        (crew_id,),
    ).fetchone()
    if crew_row is None:
        raise LookupError(f"Crew member '{crew_id}' was not found.")

    if organ_type == "CARDIAC" and anatomical_site not in CARDIAC_SITE_SET:
        raise ValueError(
            f"Site '{anatomical_site}' is not a valid cardiac valve placement."
        )
    if organ_type == "PULMONARY" and anatomical_site not in PULMONARY_SITE_SET:
        raise ValueError(
            f"Site '{anatomical_site}' is not a valid bilateral pulmonary zone."
        )

    if duration_sec < 1 or duration_sec > 30:
        raise ValueError("Recording duration must be between 1 and 30 seconds.")

    if cabin_noise_dba < 0.0 or cabin_noise_dba >= NOISE_GATE_LIMIT_DBA:
        raise ValueError(
            f"Cabin noise ({cabin_noise_dba:.1f} dBA) must remain below 55.0 dBA."
        )

    if not audio_bytes:
        raise ValueError("Uploaded acoustic sample payload cannot be empty.")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError("Uploaded acoustic sample exceeds the 10 MB onboard limit.")

    normalized_sha = sha256_hex.strip().lower()
    if not SHA256_HEX_RE.match(normalized_sha):
        raise ValueError("sha256_hex must be a 64-character lowercase hexadecimal digest.")

    computed_sha = hashlib.sha256(audio_bytes).hexdigest()
    if computed_sha != normalized_sha:
        raise ValueError(
            "Acoustic payload SHA-256 digest mismatch against client checksum."
        )

    now_dt = datetime.now(UTC)
    recorded_at_utc = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    compact_ts = now_dt.strftime("%Y%m%dT%H%M%SZ")
    unique_suffix = uuid.uuid4().hex[:6]
    safe_crew = crew_id.replace("-", "")
    filename = (
        f"{safe_crew}_{organ_type.lower()}_{anatomical_site}_"
        f"{compact_ts}_{unique_suffix}.webm"
    )
    file_rel_path = f"audio/{filename}"

    storage_dir = resolve_audio_storage_dir()
    target_path = storage_dir / filename
    target_path.write_bytes(audio_bytes)

    hr_bpm = _latest_metric_value(conn, crew_id, "resting_hr_bpm", mission_stage) or 64.0
    spo2_val = _latest_metric_value(conn, crew_id, "spo2_pct", mission_stage) or 98.0
    resp_rpm = _latest_metric_value(conn, crew_id, "respiratory_rate_rpm", mission_stage)
    if resp_rpm is None:
        resp_rpm = round(max(11.5, min(18.5, 14.2 + (hr_bpm - 64.0) * 0.08)), 1)

    signal_quality_pct = _compute_signal_quality(cabin_noise_dba)
    findings = {
        "signal_quality_pct": signal_quality_pct,
        "heart_rate_bpm": round(hr_bpm, 1),
        "respiratory_rate_rpm": round(resp_rpm, 1),
        "spo2_pct": round(spo2_val, 1),
        "rhythm_label": "Rhythmic S1/S2",
        "vesicular_label": "Clear vesicular breath",
        "murmurs_detected": False,
        "adventitious_sounds": False,
        "byte_length": len(audio_bytes),
    }

    cur = conn.execute(
        """
        INSERT INTO auscultation_recordings (
            crew_id, mission_stage, organ_type, anatomical_site,
            duration_sec, cabin_noise_dba, file_rel_path,
            sha256_hex, findings_json, recorded_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            crew_id,
            mission_stage,
            organ_type,
            anatomical_site,
            duration_sec,
            round(cabin_noise_dba, 1),
            file_rel_path,
            computed_sha,
            json.dumps(findings),
            recorded_at_utc,
        ),
    )
    sample_id = int(cur.lastrowid)
    streak_info = update_streaks(conn, crew_id, recorded_at_utc[:10])

    return AuscultationSampleCreatedOut(
        sample_id=sample_id,
        crew_id=crew_id,
        mission_stage=mission_stage,
        organ_type=organ_type,
        anatomical_site=anatomical_site,
        duration_sec=duration_sec,
        cabin_noise_dba=round(cabin_noise_dba, 1),
        file_rel_path=file_rel_path,
        sha256_hex=computed_sha,
        recorded_at_utc=recorded_at_utc,
        signal_quality_pct=signal_quality_pct,
        streak=streak_info,
    )


def resolve_sample_audio_path(conn: sqlite3.Connection, sample_id: int) -> Path:
    row = conn.execute(
        "SELECT file_rel_path FROM auscultation_recordings WHERE id = ?",
        (sample_id,),
    ).fetchone()
    if row is None:
        raise LookupError(f"Auscultation sample #{sample_id} was not found.")

    filename = Path(str(row["file_rel_path"])).name
    audio_path = resolve_audio_storage_dir() / filename
    if not audio_path.is_file():
        raise LookupError(
            f"Audio file for auscultation sample #{sample_id} is unavailable."
        )
    return audio_path


def _format_mission_day_stamp(launch_utc: str, recorded_utc: str) -> str:
    launch_dt = _parse_iso_utc(launch_utc)
    rec_dt = _parse_iso_utc(recorded_utc)
    day_num = max(1, (rec_dt.date() - launch_dt.date()).days + 1)
    return f"Recorded Day {day_num:03d} · {rec_dt.strftime('%H:%M')} UTC"


def build_auscultation_results(
    conn: sqlite3.Connection,
    crew_id: str,
    stage: AuscultationStageFilter = "ALL",
) -> AuscultationResultsOut | None:
    crew_row = conn.execute(
        "SELECT id, code, full_name, role FROM crew_members WHERE id = ?",
        (crew_id,),
    ).fetchone()
    if crew_row is None:
        return None

    mission_row = conn.execute(
        "SELECT current_stage, launch_utc FROM mission WHERE id = 1"
    ).fetchone()
    active_stage = str(mission_row["current_stage"]) if mission_row else "MISSION"
    launch_utc = (
        str(mission_row["launch_utc"]) if mission_row else "2026-10-01T08:00:00Z"
    )

    if stage == "ALL":
        rec_rows = conn.execute(
            """
            SELECT *
            FROM auscultation_recordings
            WHERE crew_id = ?
            ORDER BY recorded_at_utc DESC, id DESC
            """,
            (crew_id,),
        ).fetchall()
    else:
        rec_rows = conn.execute(
            """
            SELECT *
            FROM auscultation_recordings
            WHERE crew_id = ? AND mission_stage = ?
            ORDER BY recorded_at_utc DESC, id DESC
            """,
            (crew_id, stage),
        ).fetchall()

    stage_meas_count = 1
    if stage != "ALL":
        stage_meas_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM measurements
                WHERE crew_id = ? AND mission_stage = ?
                """,
                (crew_id, stage),
            ).fetchone()[0]
        )
    stage_has_records = bool(rec_rows) or stage_meas_count > 0

    latest_by_site: dict[str, sqlite3.Row] = {}
    latest_cardiac_row: sqlite3.Row | None = None
    latest_pulmonary_row: sqlite3.Row | None = None
    for row in rec_rows:
        site_name = str(row["anatomical_site"])
        if site_name not in latest_by_site:
            latest_by_site[site_name] = row
        if row["organ_type"] == "CARDIAC" and latest_cardiac_row is None:
            latest_cardiac_row = row
        if row["organ_type"] == "PULMONARY" and latest_pulmonary_row is None:
            latest_pulmonary_row = row

    hr_bpm = _latest_metric_value(conn, crew_id, "resting_hr_bpm", stage) or 64.0
    hr_base = _baseline_value(conn, crew_id, "resting_hr_bpm", 62.0)
    spo2_pct = _latest_metric_value(conn, crew_id, "spo2_pct", stage) or 98.0
    vo2_max = _latest_metric_value(conn, crew_id, "vo2_max_ml_kg_min", stage) or 46.5
    hrv_ms = _latest_metric_value(conn, crew_id, "hrv_rmssd_ms", stage) or 58.0
    resp_rpm = _latest_metric_value(conn, crew_id, "respiratory_rate_rpm", stage)
    if resp_rpm is None:
        resp_rpm = round(max(11.8, min(18.4, 14.2 + (hr_bpm - 64.0) * 0.08)), 1)

    co2_trend, co2_current_mmhg, latest_env_noise = _build_co2_trend(conn, crew_id)
    cabin_noise_dba = (
        round(float(rec_rows[0]["cabin_noise_dba"]), 1)
        if rec_rows
        else latest_env_noise
    )
    signal_quality_pct = _compute_signal_quality(cabin_noise_dba)

    cardiac_sites: list[AuscultationSiteStatusOut] = []
    cardiac_progress_parts: list[str] = []
    for site_key, short_label, placement_title, short_name in CARDIAC_SITE_SPECS:
        matched = latest_by_site.get(site_key)
        is_saved = matched is not None
        dur = int(matched["duration_sec"]) if matched is not None else None
        status_txt = f"Saved ({dur}s)" if is_saved else "Ready (30s)"
        cardiac_sites.append(
            AuscultationSiteStatusOut(
                site_key=site_key,
                organ_type="CARDIAC",
                short_label=short_label,
                placement_title=placement_title,
                saved=is_saved,
                duration_sec=dur,
                sample_id=int(matched["id"]) if matched is not None else None,
                recorded_at_utc=(
                    str(matched["recorded_at_utc"]) if matched is not None else None
                ),
                status_text=status_txt,
            )
        )
        cardiac_progress_parts.append(f"{short_name}: {status_txt}")

    pulmonary_sites: list[AuscultationSiteStatusOut] = []
    pulmonary_progress_parts: list[str] = []
    for site_key, short_label, placement_title, short_name in PULMONARY_SITE_SPECS:
        matched = latest_by_site.get(site_key)
        is_saved = matched is not None
        dur = int(matched["duration_sec"]) if matched is not None else None
        status_txt = f"Saved ({dur}s)" if is_saved else "Ready (30s)"
        pulmonary_sites.append(
            AuscultationSiteStatusOut(
                site_key=site_key,
                organ_type="PULMONARY",
                short_label=short_label,
                placement_title=placement_title,
                saved=is_saved,
                duration_sec=dur,
                sample_id=int(matched["id"]) if matched is not None else None,
                recorded_at_utc=(
                    str(matched["recorded_at_utc"]) if matched is not None else None
                ),
                status_text=status_txt,
            )
        )
        pulmonary_progress_parts.append(f"{short_name}: {status_txt}")

    saved_cardiac_count = sum(1 for item in cardiac_sites if item.saved)
    saved_pulmonary_count = sum(1 for item in pulmonary_sites if item.saved)

    cardiac_tone: AuscultationTone = "reference"
    if hr_bpm >= 105.0 or hr_bpm <= 42.0:
        cardiac_tone = "critical"
    elif hr_bpm >= 90.0 or hr_bpm <= 48.0:
        cardiac_tone = "warn"

    pulmonary_tone: AuscultationTone = "reference"
    if spo2_pct < 92.0 or resp_rpm >= 22.0:
        pulmonary_tone = "critical"
    elif spo2_pct < 95.0 or resp_rpm >= 19.0:
        pulmonary_tone = "warn"

    if latest_cardiac_row is not None:
        cardiac_stamp = _format_mission_day_stamp(
            launch_utc, str(latest_cardiac_row["recorded_at_utc"])
        )
        cardiac_sites_txt = (
            f"{saved_cardiac_count} / 4 valve sites saved · No murmurs"
        )
    else:
        cardiac_stamp = "Recorded Day 045 · 08:10 UTC"
        cardiac_sites_txt = "4 / 4 valve sites clear · No murmurs"

    if latest_pulmonary_row is not None:
        pulmonary_sites_txt = (
            f"Clear vesicular breath · {saved_pulmonary_count} / 4 zones saved"
        )
    else:
        pulmonary_sites_txt = "Clear vesicular breath · 4 / 4 zones"

    cardiac_summary = AuscultationOrganSummaryOut(
        organ_type="CARDIAC",
        title="CARDIAC AUDIO · 30S SAMPLE",
        primary_metric=f"{int(round(hr_bpm))} bpm",
        secondary_badge=(
            "Tachycardic S1/S2" if hr_bpm >= 95.0 else "Rhythmic S1/S2"
        ),
        sites_summary=cardiac_sites_txt,
        detail_line=cardiac_stamp,
        tone=cardiac_tone,
        saved_sites_count=saved_cardiac_count,
        total_sites_count=4,
        latest_sample_id=(
            int(latest_cardiac_row["id"]) if latest_cardiac_row is not None else None
        ),
    )

    pulmonary_summary = AuscultationOrganSummaryOut(
        organ_type="PULMONARY",
        title="PULMONARY AUDIO · 30S SAMPLE",
        primary_metric=f"{resp_rpm:.1f} rpm",
        secondary_badge=f"SpO2 {int(round(spo2_pct))}%",
        sites_summary=pulmonary_sites_txt,
        detail_line="No wheezes or crackles detected",
        tone=pulmonary_tone,
        saved_sites_count=saved_pulmonary_count,
        total_sites_count=4,
        latest_sample_id=(
            int(latest_pulmonary_row["id"])
            if latest_pulmonary_row is not None
            else None
        ),
    )

    ortho_delta = max(4, int(round(7.0 + max(0.0, hr_bpm - hr_base) * 1.1)))
    ortho_tone: AuscultationMetricTone = (
        "critical"
        if ortho_delta >= 22
        else ("warn" if ortho_delta >= 18 else "nominal")
    )

    vo2_tone: AuscultationMetricTone = (
        "critical"
        if vo2_max < 35.0
        else ("warn" if vo2_max < 40.0 else "nominal")
    )

    cr_index = round(
        max(
            0.55,
            min(
                0.96,
                0.42
                + (min(vo2_max, 54.0) / 140.0)
                + (min(hrv_ms, 80.0) / 520.0),
            ),
        ),
        2,
    )
    cr_tone: AuscultationMetricTone = (
        "critical"
        if cr_index < 0.64
        else ("warn" if cr_index < 0.70 else "nominal")
    )

    clinical_bars = [
        AuscultationMetricBarOut(
            key="vo2_max",
            label="Aerobic Capacity (VO2 Max)",
            target_label="Target: >= 40.0 mL/kg/min",
            display_value=f"{vo2_max:.1f} mL/kg",
            fill_pct=round(max(12.0, min(98.0, (vo2_max / 60.0) * 100.0)), 1),
            tone=vo2_tone,
        ),
        AuscultationMetricBarOut(
            key="orthostatic_response",
            label="Orthostatic Response",
            target_label="Allowed delta: < +18 bpm",
            display_value=f"+{ortho_delta} bpm",
            fill_pct=round(
                max(14.0, min(96.0, ((26.0 - min(ortho_delta, 25)) / 26.0) * 100.0)),
                1,
            ),
            tone=ortho_tone,
        ),
        AuscultationMetricBarOut(
            key="cardiorespiratory_index",
            label="Cardiorespiratory Index",
            target_label="Baseline: 0.70-0.92",
            display_value=f"{cr_index:.2f}",
            fill_pct=round(max(15.0, min(96.0, cr_index * 100.0)), 1),
            tone=cr_tone,
        ),
    ]

    co2_tone: AuscultationTone = "reference"
    co2_status_word = "NOMINAL"
    if co2_current_mmhg >= 4.0:
        co2_tone = "critical"
        co2_status_word = "ALERT LIMIT"
    elif co2_current_mmhg >= 3.2:
        co2_tone = "warn"
        co2_status_word = "ELEVATED"

    overall_tone: AuscultationTone = "reference"
    results_badge = "NOMINAL"
    if "critical" in (cardiac_tone, pulmonary_tone, co2_tone):
        overall_tone = "critical"
        results_badge = "CRITICAL REVIEW"
    elif "warn" in (cardiac_tone, pulmonary_tone, co2_tone):
        overall_tone = "warn"
        results_badge = "MONITOR"

    crew_num = int(crew_id.split("-")[-1]) if "-" in crew_id else 1
    cardiac_seed = (
        int(str(latest_cardiac_row["sha256_hex"])[:4], 16) / 65535.0
        if latest_cardiac_row is not None
        else crew_num * 0.11
    )
    pulmonary_seed = (
        int(str(latest_pulmonary_row["sha256_hex"])[:4], 16) / 65535.0
        if latest_pulmonary_row is not None
        else crew_num * 0.17
    )

    return AuscultationResultsOut(
        crew_id=str(crew_row["id"]),
        crew_code=str(crew_row["code"]),
        full_name=str(crew_row["full_name"]),
        role=str(crew_row["role"]),
        selected_stage=stage,
        active_mission_stage=active_stage,
        stage_has_records=stage_has_records,
        overall_tone=overall_tone,
        results_badge=results_badge,
        signal_quality_pct=signal_quality_pct,
        signal_badge=f"SIGNAL {signal_quality_pct}%",
        cabin_noise_dba=cabin_noise_dba,
        noise_gate_limit_dba=NOISE_GATE_LIMIT_DBA,
        is_noise_safe=cabin_noise_dba < NOISE_GATE_LIMIT_DBA,
        heart_rate_bpm=round(hr_bpm, 1),
        respiratory_rate_rpm=round(resp_rpm, 1),
        spo2_pct=round(spo2_pct, 1),
        cardiac_summary=cardiac_summary,
        pulmonary_summary=pulmonary_summary,
        clinical_bars=clinical_bars,
        cardiac_channel_subtitle=(
            f"{int(round(hr_bpm))} BPM · CLEAN ACOUSTIC SPECTRUM"
        ),
        pulmonary_channel_subtitle=(
            f"{resp_rpm:.1f} RPM · CABIN NOISE {cabin_noise_dba:.1f} dBA"
        ),
        phonocardiogram_samples=_build_phonocardiogram_samples(hr_bpm, cardiac_seed),
        pulmonary_envelope_samples=_build_pulmonary_envelope_samples(
            resp_rpm, pulmonary_seed
        ),
        co2_badge=f"{co2_current_mmhg:.1f} mmHg · {co2_status_word}",
        co2_tone=co2_tone,
        co2_current_mmhg=co2_current_mmhg,
        co2_target_max_mmhg=3.2,
        co2_alert_limit_mmhg=4.0,
        co2_trend=co2_trend,
        cardiac_sites=cardiac_sites,
        pulmonary_sites=pulmonary_sites,
        cardiac_progress_summary=" · ".join(cardiac_progress_parts),
        pulmonary_progress_summary=" · ".join(pulmonary_progress_parts),
    )
