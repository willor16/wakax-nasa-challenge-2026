"""Physician review of suspicious heart and lung recordings (M5).

When the onboard sound classifier hears a non-normal pattern (suspected murmur, gallop,
irregular rhythm, wheeze, crackles, diminished breath sounds) with enough confidence, or
the breathing rate from the recording is outside its limits:

1. a finding is stored as PENDING_REVIEW for the crew physician, with an immediate
   deterministic interpretation built from validated care steps;
2. the crew member gets an advisory asking for a listening review;
3. the local assistant then rewrites the interpretation in the background, grounded in
   the cardiorespiratory protocols of the guide and cross-checked with blood oxygen,
   aerobic capacity and cabin CO2. If it is not available, the deterministic text stays.

The finding appears in Notifications -> Pending Reviews like any assisted finding, and the
physician approves, rejects or promotes it to the guide with the usual review flow.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from typing import Any

import httpx

from app.db import open_connection
from app.services import reference_ranges
from app.services.alert_engine import raise_wellbeing_alert
from app.services.alert_rules import Severity
from app.services.clinical_view import latest
from app.services.environment import co2_trend
from app.services.guide import get_article, search_articles
from app.services.llm import acoustic_fallback, generate_acoustic_guidance
from app.services.mission_clock import current_stage, parse_iso, to_iso, utc_now

MIN_CONFIDENCE_PCT = 60.0
REPEAT_WINDOW = timedelta(hours=24)
MODEL_TAG = "sound-classifier"

# Guide protocol and care-step group behind each sound class.
SOUND_PATTERNS: dict[str, dict[str, str]] = {
    "systolic_murmur_suspected": {"group": "heart", "article": "wiki-cardio-01"},
    "extra_gallop_sound": {"group": "heart", "article": "wiki-cardio-01"},
    "irregular_rhythm": {"group": "heart", "article": "wiki-cardio-01"},
    "wheeze_suspected": {"group": "breathing", "article": "wiki-co2-01"},
    "crackle_suspected": {"group": "breathing", "article": "wiki-co2-01"},
    "diminished_breath_sounds": {"group": "breathing", "article": "wiki-co2-01"},
    "breathing_rate": {"group": "breathing", "article": "wiki-co2-01"},
}


def review_reason(
    organ_type: str, classification: dict | None, rate_per_min: float | None
) -> str | None:
    """Pattern key to review, or None when the recording sounds normal."""
    if (
        classification
        and classification["needs_review"]
        and classification["confidence_pct"] >= MIN_CONFIDENCE_PCT
    ):
        return classification["class_key"]
    if organ_type == "PULMONARY" and rate_per_min is not None:
        limits = reference_ranges.metric("respiratory_rate_brpm") or {}
        low, high = limits.get("nominal_min", 12), limits.get("nominal_max", 20)
        if rate_per_min < low or rate_per_min > high:
            return "breathing_rate"
    return None


def _session(organ_type: str, site: str, findings: dict, reason: str) -> dict[str, Any]:
    classification = findings.get("classification") or {}
    rate = findings.get("rate_per_min")
    unit = "beats/min" if organ_type == "CARDIAC" else "breaths/min"
    if reason == "breathing_rate":
        label = "Fast breathing" if rate and rate > 20 else "Slow breathing"
        confidence = 100.0
    else:
        label = classification.get("class_label_en", "Unusual sound")
        confidence = classification.get("confidence_pct", 0.0)
    return {
        "organ_type": organ_type,
        "site": site,
        "label_en": label,
        "confidence_pct": confidence,
        "probabilities": classification.get("probabilities", {}),
        "rate_text": f"{rate:g} {unit}" if rate else "not measurable",
    }


def _context(conn: sqlite3.Connection, crew_id: str) -> dict[str, str | None]:
    """Blood oxygen, aerobic capacity and the 24 h cabin CO2 average, for cross-checking."""
    spo2 = latest(conn, crew_id, "spo2_pct")
    vo2 = latest(conn, crew_id, "vo2_max_ml_kg_min")
    co2 = co2_trend(conn, "24h")
    co2_avg = sum(p["co2_mmhg"] for p in co2) / len(co2) if co2 else None
    return {
        "Blood oxygen": f"{spo2['value_num']:g}%" if spo2 else None,
        "Aerobic capacity": f"{vo2['value_num']:g} mL/kg/min" if vo2 else None,
        "Cabin CO2 (24 h average)": f"{co2_avg:.1f} mmHg" if co2_avg is not None else None,
    }


def _articles(conn: sqlite3.Connection, reason: str) -> list[dict]:
    primary = get_article(conn, SOUND_PATTERNS[reason]["article"])
    articles = [primary] if primary else []
    for extra in search_articles(conn, "breathing heart", loose=True)[:4]:
        if all(extra["id"] != a["id"] for a in articles) and len(articles) < 3:
            articles.append(extra)
    return articles


def open_finding(
    conn: sqlite3.Connection,
    crew_id: str,
    recording_id: int,
    organ_type: str,
    site: str,
    findings: dict,
    reason: str,
) -> dict[str, Any]:
    """Store (or reuse) the PENDING_REVIEW finding and raise the advisory. Returns ids."""
    pattern_key = f"auscultation_{reason}"
    now = utc_now()
    existing = conn.execute(
        """SELECT id FROM diagnoses WHERE crew_id = ? AND pattern_key = ?
           AND validation_status = 'PENDING_REVIEW' AND created_at_utc >= ?
           ORDER BY id DESC LIMIT 1""",
        (crew_id, pattern_key, to_iso(now - REPEAT_WINDOW)),
    ).fetchone()
    session = _session(organ_type, site, findings, reason)
    if existing:
        return {
            "finding_id": int(existing["id"]),
            "repeated": True,
            "alert_id": None,
            "session": session,
        }

    group = SOUND_PATTERNS[reason]["group"]
    article = get_article(conn, SOUND_PATTERNS[reason]["article"])
    guidance = acoustic_fallback(session, group, article)
    classification = findings.get("classification") or {}
    label = (
        f"{session['label_en']} on the {'heart' if organ_type == 'CARDIAC' else 'lung'} recording"
    )
    top = [
        {
            "display_name_en": f"{'Heart' if organ_type == 'CARDIAC' else 'Lung'} sound "
            f"({site.replace('_', ' ')})",
            "value": session["confidence_pct"],
            "unit": "% likely",
            "baseline": 0,
            "z": 0,
            "recording_id": recording_id,
        }
    ]
    if findings.get("rate_per_min"):
        top.append(
            {
                "display_name_en": "Rate from the recording",
                "value": findings["rate_per_min"],
                "unit": "per min",
                "baseline": 0,
                "z": 0,
            }
        )
    cursor = conn.execute(
        """INSERT INTO diagnoses (
               crew_id, mission_stage, anomaly_score, is_anomaly, model_name, llm_summary_en,
               preventive_steps_json, cited_article_ids_json, created_at_utc,
               pattern_key, pattern_label_en, top_metrics_json, guidance_source)
           VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            crew_id,
            current_stage(conn),
            round(session["confidence_pct"] / 100, 3),
            f"{MODEL_TAG} v{classification.get('model_version', '-')} | care-steps",
            guidance.summary_en,
            json.dumps(guidance.steps),
            json.dumps(guidance.cited_article_ids),
            to_iso(now),
            pattern_key,
            label,
            json.dumps(top),
            guidance.source,
        ),
    )
    severity = Severity.WARNING if session["confidence_pct"] >= 80 else Severity.INFO
    alert_id = raise_wellbeing_alert(
        conn,
        crew_id,
        severity,
        f"{session['label_en']} - physician listening review",
        f"The {'heart' if organ_type == 'CARDIAC' else 'lung'} recording at the "
        f"{site.replace('_', ' ')} spot needs the crew physician to listen to it. "
        "Follow the care steps meanwhile.",
        group,
        to_iso(now),
        category="AUSCULTATION",
    )
    return {
        "finding_id": int(cursor.lastrowid),
        "repeated": False,
        "alert_id": alert_id,
        "session": session,
    }


def refine_finding(finding_id: int, client: httpx.Client | None = None) -> str:
    """Background step: ask the local assistant to rewrite the interpretation.

    Returns the source kept ("assistant" or "fallback"). Never raises: a slow or missing
    assistant simply leaves the deterministic interpretation in place.
    """
    with open_connection() as conn:
        row = conn.execute("SELECT * FROM diagnoses WHERE id = ?", (finding_id,)).fetchone()
        if row is None or row["validation_status"] != "PENDING_REVIEW":
            return "fallback"
        reason = (row["pattern_key"] or "").removeprefix("auscultation_")
        if reason not in SOUND_PATTERNS:
            return "fallback"
        top = json.loads(row["top_metrics_json"] or "[]")
        recording_id = top[0].get("recording_id") if top else None
        recording = conn.execute(
            "SELECT * FROM auscultation_recordings WHERE id = ?", (recording_id,)
        ).fetchone()
        if recording is None:
            return "fallback"
        findings = json.loads(recording["findings_json"] or "{}")
        session = _session(recording["organ_type"], recording["anatomical_site"], findings, reason)
        context = _context(conn, row["crew_id"])
        articles = _articles(conn, reason)
    # No database connection is held while the assistant writes its answer.
    guidance = generate_acoustic_guidance(
        session, context, articles, SOUND_PATTERNS[reason]["group"], client=client
    )
    if guidance.source != "assistant":
        return "fallback"
    with open_connection() as conn:
        conn.execute(
            """UPDATE diagnoses SET llm_summary_en = ?, preventive_steps_json = ?,
               cited_article_ids_json = ?, guidance_source = ?,
               model_name = substr(model_name, 1, instr(model_name, '|')) || ' ' || ?
               WHERE id = ? AND validation_status = 'PENDING_REVIEW'""",
            (
                guidance.summary_en,
                json.dumps(guidance.steps),
                json.dumps(guidance.cited_article_ids),
                guidance.source,
                guidance.model,
                finding_id,
            ),
        )
        conn.commit()
    return "assistant"


def interpretation_for(
    conn: sqlite3.Connection, crew_id: str, organ_type: str, newest_utc: str | None
) -> dict | None:
    """The latest sound finding of this organ, as shown on the results screen.

    A repeated suspicious recording reuses the open finding, so the finding is looked up by
    crew member and organ (any recording within the repeat window), not by one recording.
    """
    if newest_utc is None:
        return None
    since = to_iso(parse_iso(newest_utc) - REPEAT_WINDOW)
    row = conn.execute(
        """SELECT d.*, v.full_name AS reviewer FROM diagnoses AS d
           LEFT JOIN crew_members AS v ON v.id = d.validated_by
           WHERE d.crew_id = ? AND d.pattern_key LIKE 'auscultation_%'
             AND d.created_at_utc >= ?
             AND EXISTS (
               SELECT 1 FROM json_each(d.top_metrics_json) AS j
               JOIN auscultation_recordings AS r
                 ON r.id = json_extract(j.value, '$.recording_id')
               WHERE r.organ_type = ?)
           ORDER BY d.id DESC LIMIT 1""",
        (crew_id, since, organ_type),
    ).fetchone()
    if row is None:
        return None
    return {
        "finding_id": int(row["id"]),
        "status": row["validation_status"],
        "label_en": row["pattern_label_en"],
        "summary_en": row["llm_summary_en"],
        "steps": json.loads(row["preventive_steps_json"] or "[]"),
        "source": row["guidance_source"],
        "reviewed_by": row["reviewer"],
        "reviewed_at_utc": row["validated_at_utc"],
        "created_at_utc": row["created_at_utc"],
        "age_hours": round(
            (utc_now() - parse_iso(row["created_at_utc"])).total_seconds() / 3600, 1
        ),
    }
