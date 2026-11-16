"""Complete clinical record of one crew member, for the crew physician (M9).

Everything comes straight from the onboard record: profile, pre-flight baselines against
the latest in-flight value, every reading (filterable), labs, sleep, eye exams, heart and
lung recordings, all advisories (open and acknowledged) and the reviewed findings.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.services import reference_ranges
from app.services.alert_rules import Baseline, z_score
from app.services.diagnosis import list_diagnoses

CATEGORIES = ("VITALS", "BIOMETRICS", "RESPIRATORY", "VISION", "LABS", "HABITS")
TIMELINE_LIMIT = 200


def _json(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw) if raw else default
    except json.JSONDecodeError:
        return default


def patient_list(conn: sqlite3.Connection) -> list[dict]:
    """Active crew members with their open advisories, for the physician's patient switch."""
    rows = conn.execute(
        """SELECT c.id, c.code, c.full_name, c.role, c.title_en, c.sex,
                  SUM(CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END) AS open_alerts,
                  SUM(CASE WHEN a.severity = 'CRITICAL' THEN 1 ELSE 0 END) AS open_critical
           FROM crew_members AS c
           LEFT JOIN alerts AS a ON a.crew_id = c.id AND a.acknowledged_at_utc IS NULL
           WHERE c.is_active = 1 GROUP BY c.id ORDER BY c.code"""
    ).fetchall()
    out = []
    for r in rows:
        parts = r["full_name"].split()
        out.append({
            "id": r["id"], "code": r["code"], "full_name": r["full_name"],
            "short_name": f"{parts[0][0]}. {parts[-1]}" if len(parts) > 1 else r["full_name"],
            "role": r["role"], "title_en": r["title_en"], "sex": r["sex"],
            "open_alerts": int(r["open_alerts"] or 0),
            "open_critical": int(r["open_critical"] or 0),
        })
    return out


def _baselines(conn: sqlite3.Connection, crew_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT b.metric_key, b.mean_val, b.std_dev, b.sample_count, c.display_name_en,
                  c.unit, c.category,
                  (SELECT value_num FROM measurements m WHERE m.crew_id = b.crew_id
                     AND m.metric_key = b.metric_key AND m.mission_stage != 'LAUNCH'
                     AND m.value_num IS NOT NULL
                   ORDER BY m.recorded_at_utc DESC, m.id DESC LIMIT 1) AS current,
                  (SELECT recorded_at_utc FROM measurements m WHERE m.crew_id = b.crew_id
                     AND m.metric_key = b.metric_key AND m.mission_stage != 'LAUNCH'
                   ORDER BY m.recorded_at_utc DESC, m.id DESC LIMIT 1) AS current_at_utc
           FROM baselines AS b JOIN metric_catalog AS c ON c.metric_key = b.metric_key
           WHERE b.crew_id = ? ORDER BY c.category, c.display_name_en""",
        (crew_id,),
    ).fetchall()
    result = []
    for r in rows:
        floor = (reference_ranges.metric(r["metric_key"]) or {}).get("drift_sd_floor", 0.0)
        base = Baseline(mean_val=r["mean_val"], std_dev=r["std_dev"],
                        sample_count=r["sample_count"])
        z = z_score(r["current"], base, floor) if r["current"] is not None else None
        result.append({
            "metric_key": r["metric_key"], "label": r["display_name_en"], "unit": r["unit"],
            "category": r["category"], "baseline": round(r["mean_val"], 2),
            "current": r["current"], "current_at_utc": r["current_at_utc"],
            "z": round(z, 2) if z is not None else None,
        })
    return result


def _timeline(conn: sqlite3.Connection, crew_id: str, category: str | None,
              limit: int) -> list[dict]:
    args: list[Any] = [crew_id]
    extra = ""
    if category:
        extra = "AND c.category = ?"
        args.append(category)
    rows = conn.execute(
        f"""SELECT m.id, m.metric_key, m.value_num, m.mission_stage, m.source_type,
                   m.recorded_at_utc, c.display_name_en, c.unit, c.category
            FROM measurements AS m JOIN metric_catalog AS c ON c.metric_key = m.metric_key
            WHERE m.crew_id = ? AND c.category != 'ENVIRONMENT' {extra}
              AND NOT (m.source_type = 'AUTO' AND c.category = 'VITALS')
            ORDER BY m.recorded_at_utc DESC, m.id DESC LIMIT ?""",
        (*args, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def clinical_history(conn: sqlite3.Connection, crew_id: str, category: str | None = None,
                     limit: int = TIMELINE_LIMIT) -> dict | None:
    crew = conn.execute(
        """SELECT id, code, full_name, role, title_en, age, sex, blood_type, height_cm,
                  created_at_utc FROM crew_members WHERE id = ?""",
        (crew_id,),
    ).fetchone()
    if crew is None:
        return None
    labs = _timeline(conn, crew_id, "LABS", limit)
    eyes = _timeline(conn, crew_id, "VISION", limit)
    sleep = [dict(r) for r in conn.execute(
        """SELECT id, mission_stage, sleep_start_utc, sleep_end_utc, total_sleep_min,
                  sleep_score, sleep_efficiency_pct, deep_min, rem_min, light_min, awake_min
           FROM sleep_sessions WHERE crew_id = ? ORDER BY sleep_end_utc DESC LIMIT 60""",
        (crew_id,),
    )]
    sounds = [
        {**{k: r[k] for k in ("id", "organ_type", "anatomical_site", "duration_sec",
                              "cabin_noise_dba", "mission_stage", "recorded_at_utc")},
         "findings": _json(r["findings_json"], {}),
         "audio_path": f"/auscultation/samples/{r['id']}/audio"}
        for r in conn.execute(
            """SELECT * FROM auscultation_recordings WHERE crew_id = ?
               ORDER BY recorded_at_utc DESC LIMIT 40""",
            (crew_id,),
        )
    ]
    alerts = [
        {"id": r["id"], "severity": r["severity"], "category": r["category"],
         "title_en": r["title_en"], "message_en": r["message_en"],
         "created_at_utc": r["created_at_utc"], "acknowledged_at_utc": r["acknowledged_at_utc"],
         "acknowledged_by": r["acknowledged_by"], "guide_article_id": r["wiki_article_id"],
         "steps_done": _json(r["steps_done_json"], {})}
        for r in conn.execute(
            "SELECT * FROM alerts WHERE crew_id = ? ORDER BY created_at_utc DESC, id DESC",
            (crew_id,),
        )
    ]
    notes: dict[int, list[dict]] = {}
    for r in conn.execute(
        """SELECT rd.diagnosis_id, rd.decision, rd.notes_en, rd.reviewer_id, rd.decided_at_utc
           FROM review_decisions AS rd JOIN diagnoses AS d ON d.id = rd.diagnosis_id
           WHERE d.crew_id = ? ORDER BY rd.decided_at_utc""",
        (crew_id,),
    ):
        notes.setdefault(r["diagnosis_id"], []).append(dict(r))
    findings = [
        {"id": d["id"], "created_at_utc": d.get("created_at_utc"),
         "pattern_label_en": d.get("pattern_label_en"), "summary_en": d["llm_summary_en"],
         "validation_status": d["validation_status"], "anomaly_score": d["anomaly_score"],
         "reviews": notes.get(d["id"], [])}
        for d in list_diagnoses(conn, viewer_id="", viewer_role="PHYSICIAN")
        if d["crew_id"] == crew_id
    ]
    return {
        "crew": dict(crew),
        "categories": list(CATEGORIES),
        "category": category,
        "baselines": _baselines(conn, crew_id),
        "timeline": _timeline(conn, crew_id, category, limit),
        "labs": labs,
        "eyes": eyes,
        "sleep": sleep,
        "sounds": sounds,
        "alerts": alerts,
        "findings": findings,
        "counts": {"open_alerts": sum(1 for a in alerts if a["acknowledged_at_utc"] is None),
                   "findings": len(findings), "recordings": len(sounds)},
    }
