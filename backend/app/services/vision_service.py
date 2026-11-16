"""Vision & ocular exam results (screen 08): bilateral neuro-ocular follow-up.

Read-only view over the stored ocular exams. Limits come from the reference
catalog; the trend only contains measured exams (plus the pre-flight baseline
and the care target, which is clearly marked as a target, not a reading).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.services import reference_ranges
from app.services.alert_engine import CARE_STEPS
from app.services.clinical_view import baseline, crew_row, latest, metric_view
from app.services.crew_names import physician_name
from app.services.mission_clock import (
    current_stage,
    day_label,
    mission_day,
    parse_iso,
    period_since,
    to_iso,
    utc_now,
)

REVIEW_PATTERN = "ocular_review"
_ORDER = ["NO_DATA", "NOMINAL", "WATCH", "WARNING", "CRITICAL"]
_EYE_TEXT = {
    "NOMINAL": "Normal",
    "WATCH": "Watch",
    "WARNING": "Elevated",
    "CRITICAL": "Elevated",
    "NO_DATA": "No Data",
}


def eye_views(conn: sqlite3.Connection, crew_id: str) -> dict[str, dict[str, Any]]:
    """Latest optic nerve sheath reading of each eye with its status."""
    views = {}
    for side in ("left", "right"):
        view = metric_view(conn, crew_id, f"optic_sheath_{side}_mm", nominal_text="Normal")
        view["eye_text"] = _EYE_TEXT[view["status"]]
        views[side] = view
    return views


def _trend(conn: sqlite3.Connection, crew_id: str, period: str = "all") -> list[dict[str, Any]]:
    """In-flight exams in the window (one point per exam day), after the pre-flight baseline."""
    since = period_since(utc_now(), period) or "0000"
    rows = conn.execute(
        """SELECT metric_key, value_num, recorded_at_utc, mission_stage FROM measurements
           WHERE crew_id = ? AND metric_key IN ('optic_sheath_left_mm', 'optic_sheath_right_mm')
             AND mission_stage != 'LAUNCH' AND recorded_at_utc >= ?
           ORDER BY recorded_at_utc ASC, id ASC""",
        (crew_id, since),
    ).fetchall()
    exams: dict[str, dict[str, Any]] = {}
    for row in rows:
        day = row["recorded_at_utc"][:10]
        point = exams.setdefault(
            day,
            {
                "label": day_label(mission_day(conn, parse_iso(row["recorded_at_utc"]))).replace(
                    "D", "Day "
                ),
                "date_utc": day,
                "left": None,
                "right": None,
                "kind": "EXAM",
            },
        )
        point["left" if "left" in row["metric_key"] else "right"] = row["value_num"]
        point["recorded_at_utc"] = row["recorded_at_utc"]
        point["mission_stage"] = row["mission_stage"]
    points = list(exams.values())
    left, right = (baseline(conn, crew_id, f"optic_sheath_{s}_mm") for s in ("left", "right"))
    if left or right:
        points.insert(
            0,
            {
                "label": "Baseline",
                "date_utc": None,
                "recorded_at_utc": None,
                "mission_stage": "LAUNCH",
                "kind": "BASELINE",
                "left": round(left.mean_val, 2) if left else None,
                "right": round(right.mean_val, 2) if right else None,
            },
        )
    return points


def _review(conn: sqlite3.Connection, crew_id: str, exam_at: str | None, needs: bool) -> dict:
    row = conn.execute(
        """SELECT d.validation_status, d.validated_at_utc, d.physician_notes_en, c.full_name
           FROM diagnoses d LEFT JOIN crew_members c ON c.id = d.validated_by
           WHERE d.crew_id = ? AND d.pattern_key = ? ORDER BY d.id DESC LIMIT 1""",
        (crew_id, REVIEW_PATTERN),
    ).fetchone()
    if row and exam_at and row["validated_at_utc"] and row["validated_at_utc"] >= exam_at:
        return {
            "state": row["validation_status"],
            "text": f"Reviewed by {physician_name(row['full_name'])}",
            "reviewed_at_utc": row["validated_at_utc"],
            "notes_en": row["physician_notes_en"],
        }
    if exam_at is None:
        return {
            "state": "NO_EXAM",
            "text": "No exam recorded yet",
            "reviewed_at_utc": None,
            "notes_en": None,
        }
    return {
        "state": "PENDING_REVIEW" if needs else "NOT_REQUIRED",
        "text": "Awaiting physician review" if needs else "Within usual range",
        "reviewed_at_utc": None,
        "notes_en": None,
    }


_MILESTONE_ORDER = [
    "Pre-Flight Baseline",
    "Mission Day 30",
    "Mission Day 90",
    "30 Days Before Return",
    "Post-Flight Recovery",
]


def _next_milestone(current: str | None) -> str:
    if current in _MILESTONE_ORDER:
        idx = _MILESTONE_ORDER.index(current)
        if idx + 1 < len(_MILESTONE_ORDER):
            return _MILESTONE_ORDER[idx + 1]
    return "Mission Day 30"


def _is_empty_phantom_sandra(sandra: dict[str, Any]) -> bool:
    acuity_bi = sandra.get("acuity_bilateral") or {}
    if any(acuity_bi.get(side) is not None for side in ("OD", "OS", "OU")):
        return False
    amsler = sandra.get("amsler") or {}
    for eye_key in ("OD", "OS"):
        eye = amsler.get(eye_key) or {}
        if int(eye.get("affectedCount") or 0) > 0:
            return False
        perceptual = eye.get("perceptual") or {}
        if any(perceptual.get(k) is not None for k in perceptual):
            return False
    symptoms = sandra.get("symptoms") or {}
    if int(symptoms.get("risk_score") or 0) > 0 or symptoms.get("active_flags"):
        return False
    return int(symptoms.get("answered_count") or 0) <= 1


def _sandra_functional_summary(conn: sqlite3.Connection, crew_id: str) -> dict[str, Any] | None:
    rows = conn.execute(
        """SELECT value_num, payload_json, recorded_at_utc
           FROM measurements
           WHERE crew_id = ? AND metric_key = 'visual_acuity_snellen'
             AND payload_json LIKE '%sandra_test%'
           ORDER BY recorded_at_utc DESC, id DESC LIMIT 10""",
        (crew_id,),
    ).fetchall()
    parsed: list[tuple[Any, dict[str, Any]]] = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except (TypeError, ValueError):
            continue
        sandra = payload.get("sandra_test") if isinstance(payload, dict) else None
        if isinstance(sandra, dict):
            parsed.append((row, sandra))
    if not parsed:
        return None

    chosen = next(((r, s) for r, s in parsed if not _is_empty_phantom_sandra(s)), parsed[0])
    row, sandra = chosen
    milestone = str(sandra.get("milestone") or "Mission Day 30")
    amsler = sandra.get("amsler") or {}
    symptoms = sandra.get("symptoms") or {}
    raw_acuity = sandra.get("acuity_bilateral") or {}
    acuity_bi = {side: raw_acuity.get(side) for side in ("OD", "OS", "OU")}
    exam_day = str(row["recorded_at_utc"])[:10]
    for prev_row, prev_sandra in parsed:
        if prev_row["recorded_at_utc"][:10] != exam_day:
            continue
        if str(prev_sandra.get("milestone") or milestone) != milestone:
            continue
        prev_acuity = prev_sandra.get("acuity_bilateral") or {}
        for side in ("OD", "OS", "OU"):
            if acuity_bi[side] is None and prev_acuity.get(side) is not None:
                acuity_bi[side] = prev_acuity[side]

    severity = "NOMINAL"
    for eye_key in ("OD", "OS"):
        eye = amsler.get(eye_key) or {}
        if int(eye.get("scotomaCount") or 0) > 0 or eye.get("centralInvolved"):
            severity = "CRITICAL"
            break
        if int(eye.get("affectedCount") or 0) > 0 or eye.get("hasPerceptualAlert"):
            severity = "WARNING"

    triage = str(symptoms.get("triage_level") or "NOMINAL").upper()
    flags = [str(f) for f in (symptoms.get("active_flags") or [])]
    if triage == "ALERT" or "diplopia" in flags or "transient_vision_loss" in flags:
        severity = "CRITICAL"
    elif severity == "NOMINAL" and (triage == "OBSERVATION" or len(flags) > 0):
        severity = "WARNING"

    return {
        "milestone": milestone,
        "next_milestone": _next_milestone(milestone),
        "severity": severity,
        "needs_review": severity in ("WARNING", "CRITICAL"),
        "recorded_at_utc": row["recorded_at_utc"],
        "exam_day_label": day_label(mission_day(conn, parse_iso(row["recorded_at_utc"]))),
        "acuity_bilateral": acuity_bi,
        "amsler": amsler,
        "symptoms": symptoms,
    }


def _care_plan(conn: sqlite3.Connection, crew_id: str) -> list[dict[str, str]]:
    """Steps of the open ocular advisory, or the standing preventive steps."""
    row = conn.execute(
        """SELECT a.recommended_actions_json FROM alerts a JOIN measurements m
           ON m.id = a.measurement_id WHERE a.crew_id = ? AND a.acknowledged_at_utc IS NULL
           AND (m.metric_key LIKE 'optic_sheath%' OR m.metric_key = 'visual_acuity_snellen')
           ORDER BY a.id DESC LIMIT 1""",
        (crew_id,),
    ).fetchone()
    steps = (
        json.loads(row["recommended_actions_json"])
        if row
        else [dict(s) for s in CARE_STEPS["vision"]]
    )
    return steps[:3]


def build_vision_exam(
    conn: sqlite3.Connection, crew_id: str, period: str = "all"
) -> dict[str, Any] | None:
    if crew_row(conn, crew_id) is None:
        return None
    eyes = eye_views(conn, crew_id)
    worst_side = max(
        ("left", "right"), key=lambda s: (_ORDER.index(eyes[s]["status"]), eyes[s]["value"] or 0)
    )
    worst = eyes[worst_side]
    pressures = {
        s: metric_view(conn, crew_id, f"iop_{s}_mmhg", nominal_text="Normal")
        for s in ("left", "right")
    }
    pressure = max(pressures.values(), key=lambda v: (_ORDER.index(v["status"]), v["value"] or 0))
    retina = metric_view(conn, crew_id, "retinal_thickness_um", nominal_text="Stable")
    acuity = metric_view(conn, crew_id, "visual_acuity_snellen")
    functional_exam = _sandra_functional_summary(conn, crew_id)
    exam_at = max(
        [v["recorded_at_utc"] for v in eyes.values() if v["recorded_at_utc"]]
        + ([functional_exam["recorded_at_utc"]] if functional_exam else []),
        default=None,
    )
    functional_needs_review = bool(
        (functional_exam and functional_exam["needs_review"])
        or acuity["status"] in ("WARNING", "CRITICAL")
    )
    needs_review = worst["status"] in ("WARNING", "CRITICAL") or functional_needs_review
    candidates = [worst["status"]]
    if functional_exam is not None:
        candidates.append(functional_exam["severity"])
    if acuity["status"] != "NO_DATA":
        candidates.append(acuity["status"])
    effective_status = max(candidates, key=_ORDER.index)

    if worst["status"] == "NO_DATA":
        if functional_exam is not None:
            if functional_needs_review:
                headline, header = "SANS visual battery finding", "VISUAL REVIEW NEEDED"
            else:
                headline, header = "Visual battery within usual range", "VISION NOMINAL"
        else:
            headline, header = "No ocular exam recorded yet", "NO EXAM YET"
    elif functional_needs_review and _ORDER.index(effective_status) > _ORDER.index(worst["status"]):
        headline = "SANS visual battery finding noted"
        header = "VISUAL REVIEW NEEDED"
    elif worst["status"] == "NOMINAL":
        headline, header = "Both eyes within the usual range", "EYES NOMINAL"
    else:
        word = {"WATCH": "above personal baseline", "WARNING": "elevated", "CRITICAL": "elevated"}
        headline = f"{worst_side.title()} sheath {word[worst['status']]} ({worst['value']:g} mm)"
        header = f"{worst_side.upper()} EYE {'ELEVATED' if needs_review else 'WATCH'}"
    follow_up = conn.execute(
        """SELECT due_at_utc FROM scheduled_checks WHERE crew_id = ? AND check_type = 'OCULAR_EXAM'
           AND status = 'PENDING' ORDER BY due_at_utc ASC LIMIT 1""",
        (crew_id,),
    ).fetchone()
    sheath = reference_ranges.metric("optic_sheath_right_mm") or {}
    bases = [
        b for b in (baseline(conn, crew_id, f"optic_sheath_{s}_mm") for s in ("left", "right")) if b
    ]
    return {
        "crew_id": crew_id,
        "status": effective_status,
        "header_text": header,
        "headline": headline,
        "worst_side": worst_side if worst["status"] not in ("NO_DATA", "NOMINAL") else None,
        "review": _review(conn, crew_id, exam_at, needs_review),
        "eyes": eyes,
        "pressure": pressure,
        "pressures": pressures,
        "retina": retina,
        "acuity": acuity,
        "functional_exam": functional_exam,
        "exam_at_utc": exam_at,
        "exam_day_label": day_label(mission_day(conn, parse_iso(exam_at))) if exam_at else None,
        "follow_up_at_utc": follow_up["due_at_utc"] if follow_up else None,
        "follow_up_day_label": day_label(mission_day(conn, parse_iso(follow_up["due_at_utc"])))
        if follow_up
        else None,
        "trend": _trend(conn, crew_id, period),
        "period": period,
        "limits": {
            "nominal_max_mm": sheath.get("nominal_max"),
            "alert_mm": sheath.get("critical_threshold"),
            "baseline_low_mm": round(min(b.mean_val for b in bases), 2) if bases else None,
        },
        "care_plan": _care_plan(conn, crew_id),
    }


def record_vision_review(
    conn: sqlite3.Connection, crew_id: str, physician_id: str, decision: str, notes_en: str | None
) -> dict[str, Any]:
    """Physician validation of the latest ocular exam (kept with the assisted findings)."""
    if crew_row(conn, crew_id) is None:
        raise LookupError("Crew member not found.")
    exam = (
        latest(conn, crew_id, "optic_sheath_right_mm")
        or latest(conn, crew_id, "optic_sheath_left_mm")
        or latest(conn, crew_id, "visual_acuity_snellen")
    )
    if exam is None:
        raise LookupError("There is no ocular exam to review yet.")
    eyes = eye_views(conn, crew_id)
    functional = _sandra_functional_summary(conn, crew_id)
    now = to_iso(utc_now())
    parts = [
        f"{side} optic sheath {view['value']:g} mm ({view['eye_text'].lower()})"
        for side, view in eyes.items()
        if view["value"] is not None
    ]
    if functional is not None:
        parts.append(f"visual battery {functional['severity'].lower()}")
    summary = "; ".join(parts)
    top = [
        {"metric_key": v["metric_key"], "label": v["label"], "value": v["value"], "unit": v["unit"]}
        for v in eyes.values()
        if v["value"] is not None
    ]
    cursor = conn.execute(
        """INSERT INTO diagnoses (crew_id, mission_stage, anomaly_score, is_anomaly, model_name,
           llm_summary_en, preventive_steps_json, cited_article_ids_json, validation_status,
           validated_by, validated_at_utc, physician_notes_en, created_at_utc, pattern_key,
           pattern_label_en, top_metrics_json, guidance_source)
           VALUES (?, ?, 0, ?, 'physician-review', ?, ?, '["wiki-vision-01"]', ?, ?, ?, ?, ?, ?,
                   'Ocular exam review', ?, 'physician')""",
        (
            crew_id,
            current_stage(conn),
            int(any(v["status"] in ("WARNING", "CRITICAL") for v in eyes.values())),
            f"Ocular exam: {summary}.",
            json.dumps(_care_plan(conn, crew_id)),
            decision,
            physician_id,
            now,
            notes_en,
            now,
            REVIEW_PATTERN,
            json.dumps(top),
        ),
    )
    diagnosis_id = int(cursor.lastrowid)
    conn.execute(
        """INSERT INTO review_decisions (diagnosis_id, decision, reviewer_id, notes_en,
           decided_at_utc) VALUES (?, ?, ?, ?, ?)""",
        (diagnosis_id, decision, physician_id, notes_en, now),
    )
    return {
        "diagnosis_id": diagnosis_id,
        "crew_id": crew_id,
        "validation_status": decision,
        "validated_at_utc": now,
    }
