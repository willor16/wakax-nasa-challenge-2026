"""Heart and lung recordings: storage, signal screening and the results view (screen 09).

Audio files stay on disk (``storage/audio``); the database keeps the relative
path, the SHA-256 checksum and the screening numbers computed from the audio
itself by ``app.services.acoustics``. Nothing on the results screen is assumed:
a site that was not recorded is shown as not recorded.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import wave
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.config import AUDIO_STORAGE_DIR
from app.services import acoustics, reference_ranges
from app.services.clinical_view import crew_row, latest, metric_view
from app.services.contracts import evaluate_alerts
from app.services.environment import cabin_snapshot, co2_limits_mmhg, co2_trend_24h
from app.services.mission_clock import (
    current_stage,
    day_label,
    mission_day,
    parse_iso,
    to_iso,
    utc_now,
)

CARDIAC_SITES = ("aortic", "pulmonic", "tricuspid", "mitral")
PULMONARY_SITES = ("upper_left", "upper_right", "lower_left", "lower_right")
SAMPLE_SECONDS = 30
MAX_AUDIO_BYTES = 6 * 1024 * 1024
SESSION_WINDOW_HOURS = 12


def quiet_limit_dba() -> float:
    return float((reference_ranges.metric("cabin_noise_dba") or {}).get("nominal_max", 55.0))


def save_auscultation_sample(
    conn: sqlite3.Connection,
    crew_id: str,
    organ_type: str,
    anatomical_site: str,
    cabin_noise_dba: float,
    sha256_hex: str,
    audio_bytes: bytes,
    storage_dir: Path | None = None,
) -> dict:
    """Validate, analyse and store one 30-second recording."""
    if crew_row(conn, crew_id) is None:
        raise LookupError("Crew member not found.")
    sites = CARDIAC_SITES if organ_type == "CARDIAC" else PULMONARY_SITES
    if anatomical_site not in sites:
        raise ValueError("That listening spot does not belong to this recording type.")
    if cabin_noise_dba >= quiet_limit_dba():
        raise ValueError(
            f"The cabin is too loud ({cabin_noise_dba:.0f} dBA). "
            f"Record when it is below {quiet_limit_dba():.0f} dBA."
        )
    if not audio_bytes or len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError("The recording is empty or too large. Please record again.")
    if hashlib.sha256(audio_bytes).hexdigest() != sha256_hex.lower():
        raise ValueError("The recording was damaged while saving. Please record again.")
    try:
        samples, rate = acoustics.read_wav(audio_bytes)
    except (wave.Error, EOFError, KeyError) as exc:
        raise ValueError("The recording could not be read. Please record again.") from exc
    seconds = len(samples) / rate if rate else 0
    if not SAMPLE_SECONDS - 1.5 <= seconds <= SAMPLE_SECONDS + 1.5:
        raise ValueError("A full 30-second recording is needed. Please record again.")

    findings = acoustics.analyse(samples, rate, organ_type).to_dict()
    now = utc_now()
    name = f"{crew_id}_{organ_type.lower()}_{anatomical_site}_{now.strftime('%Y%m%dT%H%M%S')}.wav"
    storage_dir = storage_dir or AUDIO_STORAGE_DIR
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / name).write_bytes(audio_bytes)
    stage = current_stage(conn)
    cursor = conn.execute(
        """INSERT INTO auscultation_recordings (crew_id, mission_stage, organ_type,
           anatomical_site, duration_sec, cabin_noise_dba, file_rel_path, sha256_hex,
           findings_json, recorded_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            crew_id,
            stage,
            organ_type,
            anatomical_site,
            SAMPLE_SECONDS,
            cabin_noise_dba,
            f"audio/{name}",
            sha256_hex.lower(),
            json.dumps(findings),
            to_iso(now),
        ),
    )
    alerts: list[int] = []
    if organ_type == "PULMONARY" and findings["rate_per_min"] is not None:
        measurement = conn.execute(
            """INSERT INTO measurements (crew_id, metric_key, mission_stage, source_type,
               recorded_at_utc, value_num, payload_json)
               VALUES (?, 'respiratory_rate_brpm', ?, 'AUTO', ?, ?, ?)""",
            (
                crew_id,
                stage,
                to_iso(now),
                findings["rate_per_min"],
                json.dumps({"from_recording_id": int(cursor.lastrowid)}),
            ),
        )
        alerts = evaluate_alerts(conn, int(measurement.lastrowid))
    return {
        "id": int(cursor.lastrowid),
        "organ_type": organ_type,
        "anatomical_site": anatomical_site,
        "recorded_at_utc": to_iso(now),
        "rate_per_min": findings["rate_per_min"],
        "regularity_pct": findings["regularity_pct"],
        "signal_quality_pct": findings["signal_quality_pct"],
        "rhythm_label": findings["rhythm_label"],
        "alerts_created": alerts,
    }


def resolve_sample_audio(conn: sqlite3.Connection, sample_id: int) -> tuple[Path, str]:
    """``(file path, crew_id)`` of a stored recording, verified against its checksum."""
    row = conn.execute(
        "SELECT crew_id, file_rel_path, sha256_hex FROM auscultation_recordings WHERE id = ?",
        (sample_id,),
    ).fetchone()
    if row is None:
        raise LookupError("Recording not found.")
    path = AUDIO_STORAGE_DIR / Path(row["file_rel_path"]).name
    if not path.is_file():
        raise LookupError("The audio file of this recording is no longer on board.")
    if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256_hex"]:
        raise LookupError("The audio file of this recording is damaged.")
    return path, row["crew_id"]


def _session(conn: sqlite3.Connection, crew_id: str, organ_type: str) -> list[dict[str, Any]]:
    """Latest recording of each site within the most recent recording session."""
    newest = conn.execute(
        "SELECT MAX(recorded_at_utc) FROM auscultation_recordings "
        "WHERE crew_id = ? AND organ_type = ?",
        (crew_id, organ_type),
    ).fetchone()[0]
    if newest is None:
        return []
    since = to_iso(parse_iso(newest).replace(microsecond=0) - timedelta(hours=SESSION_WINDOW_HOURS))
    rows = conn.execute(
        """SELECT id, anatomical_site, cabin_noise_dba, findings_json, recorded_at_utc
           FROM auscultation_recordings WHERE crew_id = ? AND organ_type = ?
           AND recorded_at_utc >= ? ORDER BY recorded_at_utc DESC, id DESC""",
        (crew_id, organ_type, since),
    ).fetchall()
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["anatomical_site"] not in seen:
            seen[row["anatomical_site"]] = {
                "id": row["id"],
                "site": row["anatomical_site"],
                "cabin_noise_dba": row["cabin_noise_dba"],
                "recorded_at_utc": row["recorded_at_utc"],
                **json.loads(row["findings_json"] or "{}"),
            }
    return list(seen.values())


def _organ_summary(conn: sqlite3.Connection, crew_id: str, organ_type: str) -> dict | None:
    samples = _session(conn, crew_id, organ_type)
    if not samples:
        return None
    rated = [s["rate_per_min"] for s in samples if s.get("rate_per_min") is not None]
    steady = [
        s
        for s in samples
        if s.get("regularity_pct", 0) >= (45 if organ_type == "CARDIAC" else 35)
        and s.get("rate_per_min") is not None
    ]
    latest_sample = samples[0]
    preferred = next((s for s in samples if s["site"] in ("mitral", "upper_right")), latest_sample)
    regular = len(steady) == len(samples)
    if organ_type == "CARDIAC":
        text = "Rhythmic S1/S2" if regular else "Uneven rhythm"
    else:
        text = "Steady breathing" if regular else "Uneven breathing"
    return {
        "rate_per_min": round(sum(rated) / len(rated), 1) if rated else None,
        "rhythm_text": text,
        "regular": regular,
        "sites_recorded": len(samples),
        "sites_regular": len(steady),
        "sites_total": 4,
        "signal_quality_pct": round(
            sum(s.get("signal_quality_pct", 0) for s in samples) / len(samples)
        ),
        "cabin_noise_dba": latest_sample["cabin_noise_dba"],
        "recorded_at_utc": latest_sample["recorded_at_utc"],
        "day_label": day_label(mission_day(conn, parse_iso(latest_sample["recorded_at_utc"]))),
        "waveform_site": preferred["site"],
        "waveform_recording_id": preferred["id"],
        "envelope": preferred.get("envelope", []),
        "needs_physician_review": not regular,
        "samples": [
            {
                k: s[k]
                for k in (
                    "id",
                    "site",
                    "recorded_at_utc",
                    "rate_per_min",
                    "regularity_pct",
                    "signal_quality_pct",
                    "rhythm_label",
                )
                if k in s
            }
            for s in samples
        ],
    }


def cardiac_summary(conn: sqlite3.Connection, crew_id: str) -> dict | None:
    return _organ_summary(conn, crew_id, "CARDIAC")


def session_progress(conn: sqlite3.Connection, crew_id: str) -> dict[str, list[str]]:
    """Sites already saved today, for the capture screen's progress line."""
    today = utc_now().date().isoformat()
    rows = conn.execute(
        """SELECT DISTINCT organ_type, anatomical_site FROM auscultation_recordings
           WHERE crew_id = ? AND substr(recorded_at_utc, 1, 10) = ?""",
        (crew_id, today),
    ).fetchall()
    return {
        "CARDIAC": [r["anatomical_site"] for r in rows if r["organ_type"] == "CARDIAC"],
        "PULMONARY": [r["anatomical_site"] for r in rows if r["organ_type"] == "PULMONARY"],
    }


def build_auscultation_results(conn: sqlite3.Connection, crew_id: str) -> dict[str, Any] | None:
    if crew_row(conn, crew_id) is None:
        return None
    cardiac = cardiac_summary(conn, crew_id)
    pulmonary = _organ_summary(conn, crew_id, "PULMONARY")
    oxygen = latest(conn, crew_id, "spo2_pct")
    if cardiac is None and pulmonary is None:
        header, status = "NO RECORDINGS YET", "NO_DATA"
    elif (cardiac is None or cardiac["regular"]) and (pulmonary is None or pulmonary["regular"]):
        header, status = "S1/S2 & LUNGS STEADY", "NOMINAL"
    else:
        header, status = "PHYSICIAN REVIEW NEEDED", "WARNING"
    qualities = [o["signal_quality_pct"] for o in (cardiac, pulmonary) if o]
    cabin = cabin_snapshot(conn)
    trend = co2_trend_24h(conn)
    return {
        "crew_id": crew_id,
        "status": status,
        "header_text": header,
        "signal_quality_pct": round(sum(qualities) / len(qualities)) if qualities else None,
        "cardiac": cardiac,
        "pulmonary": pulmonary,
        "spo2_pct": oxygen["value_num"] if oxygen else None,
        "fitness": [
            metric_view(conn, crew_id, "vo2_max_ml_kg_min"),
            metric_view(conn, crew_id, "orthostatic_hr_delta_bpm"),
            metric_view(conn, crew_id, "cardiorespiratory_index"),
        ],
        "co2": {
            "current_mmhg": cabin["co2_mmhg"] if cabin else None,
            "status": cabin["statuses"]["co2_ppm"] if cabin else "NO_DATA",
            "limits_mmhg": co2_limits_mmhg(),
            "trend": trend,
        },
        "quiet_limit_dba": quiet_limit_dba(),
    }
