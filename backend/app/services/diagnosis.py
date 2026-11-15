"""Assisted findings and physician review (D3-04, D3-05, §3.9-3.10).

Flow: scan -> finding stored as PENDING_REVIEW (crew does not see it yet) ->
physician approves, rejects or promotes it to the guide. Approval sends the
crew member an advisory with the reviewed steps; promotion also adds a
validated case to the medical guide (the evolving guide of §3.10).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import httpx

from app.services.anomaly import PATTERN_INFO, Models, detect
from app.services.guide import get_article, search_articles
from app.services.llm import generate_guidance
from app.services.wiki_seed import ensure_guide_schema

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DECISIONS = ("APPROVED", "REJECTED", "PROMOTED_TO_GUIDE")
REPEAT_WINDOW = timedelta(hours=24)
# Guide topic used when a validated case is added to the guide.
PATTERN_CATEGORY = {
    "ocular": "Vision & Pressure",
    "fatigue": "Sleep & Fatigue",
    "low_oxygen": "CO2 Exposure",
    "dehydration": "Cardiorespiratory",
    "decoupled": "Cardiorespiratory",
    "novel": "Cardiorespiratory",
}
_EXTRA_COLUMNS = {
    "pattern_key": "TEXT",
    "pattern_label_en": "TEXT",
    "top_metrics_json": "TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(top_metrics_json))",
    "guidance_source": "TEXT",
}


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def ensure_diagnosis_columns(conn: sqlite3.Connection) -> None:
    present = {r[1] for r in conn.execute("PRAGMA table_info(diagnoses)")}
    for name, ddl in _EXTRA_COLUMNS.items():
        if name not in present:
            conn.execute(f"ALTER TABLE diagnoses ADD COLUMN {name} {ddl}")


def _mission_stage(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT current_stage FROM mission WHERE id = 1").fetchone()
    return row[0] if row else "MISSION"


def _row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["preventive_steps"] = json.loads(data.pop("preventive_steps_json") or "[]")
    data["cited_article_ids"] = json.loads(data.pop("cited_article_ids_json") or "[]")
    data["top_metrics"] = json.loads(data.pop("top_metrics_json") or "[]")
    data["is_anomaly"] = bool(data["is_anomaly"])
    return data


def get_diagnosis(conn: sqlite3.Connection, diagnosis_id: int) -> dict | None:
    ensure_diagnosis_columns(conn)
    row = conn.execute(
        """
        SELECT d.*, c.full_name AS crew_name, c.role AS crew_role
        FROM diagnoses AS d JOIN crew_members AS c ON c.id = d.crew_id
        WHERE d.id = ?
        """,
        (diagnosis_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def _grounding_articles(conn: sqlite3.Connection, pattern: str) -> list[dict]:
    """The pattern's guide protocol first, plus up to two related ones."""
    articles: list[dict] = []
    primary = get_article(conn, PATTERN_INFO[pattern]["article"])
    if primary:
        articles.append(primary)
    # Only closely related protocols (every word must match) to keep citations relevant.
    for extra in search_articles(conn, PATTERN_INFO[pattern]["label_en"], loose=False):
        if all(extra["id"] != a["id"] for a in articles):
            articles.append(extra)
    return articles[:3]


def scan_crew_member(conn: sqlite3.Connection, crew_id: str, *, models: Models | None = None,
                     client: httpx.Client | None = None) -> dict:
    """Run the networks; store a PENDING_REVIEW finding when something stands out."""
    ensure_diagnosis_columns(conn)
    conn.commit()  # nothing stays locked while the assistant writes its answer
    finding = detect(conn, crew_id, models=models)
    result = {"finding": asdict(finding), "diagnosis": None, "repeated": False}
    if not finding.is_anomaly or finding.pattern is None:
        return result

    since = (_now() - REPEAT_WINDOW).strftime(TS_FORMAT)
    existing = conn.execute(
        """
        SELECT id FROM diagnoses
        WHERE crew_id = ? AND pattern_key = ? AND validation_status = 'PENDING_REVIEW'
          AND created_at_utc >= ?
        ORDER BY id DESC LIMIT 1
        """,
        (crew_id, finding.pattern, since),
    ).fetchone()
    if existing:
        result["diagnosis"] = get_diagnosis(conn, existing[0])
        result["repeated"] = True
        return result

    info = PATTERN_INFO[finding.pattern]
    articles = _grounding_articles(conn, finding.pattern)
    guidance = generate_guidance(
        {**asdict(finding), "article_id": info["article"]}, articles, info["group"], client=client
    )
    cursor = conn.execute(
        """
        INSERT INTO diagnoses (
            crew_id, mission_stage, anomaly_score, is_anomaly, model_name, llm_summary_en,
            preventive_steps_json, cited_article_ids_json, created_at_utc,
            pattern_key, pattern_label_en, top_metrics_json, guidance_source
        ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            crew_id, _mission_stage(conn), finding.anomaly_score,
            f"{finding.model_name} | {guidance.model}", guidance.summary_en,
            json.dumps(guidance.steps), json.dumps(guidance.cited_article_ids),
            _now().strftime(TS_FORMAT), finding.pattern, finding.pattern_label_en,
            json.dumps(finding.top_metrics), guidance.source,
        ),
    )
    result["diagnosis"] = get_diagnosis(conn, int(cursor.lastrowid))
    return result


def scan_all(conn: sqlite3.Connection, **kwargs) -> list[dict]:
    """Scan every active crew member, saving after each one.

    The assistant can take many seconds per finding; committing between crew
    members keeps the database free for new readings in the meantime.
    """
    crew = [r[0] for r in conn.execute("SELECT id FROM crew_members WHERE is_active = 1")]
    results = []
    for crew_id in crew:
        results.append(scan_crew_member(conn, crew_id, **kwargs))
        conn.commit()
    return results


def list_diagnoses(conn: sqlite3.Connection, *, viewer_id: str, viewer_role: str,
                   status: str | None = None) -> list[dict]:
    """Physician: every finding (optionally by status). Crew: their own reviewed ones."""
    ensure_diagnosis_columns(conn)
    sql = """
        SELECT d.*, c.full_name AS crew_name, c.role AS crew_role
        FROM diagnoses AS d JOIN crew_members AS c ON c.id = d.crew_id
        WHERE 1 = 1
    """
    args: list[object] = []
    if viewer_role != "PHYSICIAN":
        sql += " AND d.crew_id = ? AND d.validation_status IN ('APPROVED', 'PROMOTED_TO_GUIDE')"
        args.append(viewer_id)
    elif status:
        sql += " AND d.validation_status = ?"
        args.append(status)
    sql += " ORDER BY d.created_at_utc DESC, d.id DESC"
    return [_row_to_dict(r) for r in conn.execute(sql, args)]


def _notify_crew(conn: sqlite3.Connection, diagnosis: dict, notes: str | None, stamp: str) -> int:
    message = diagnosis["llm_summary_en"]
    if notes:
        message += f" Physician note: {notes}"
    cursor = conn.execute(
        """
        INSERT INTO alerts (
            crew_id, severity, category, title_en, message_en, recommended_actions_json,
            wiki_article_id, is_quiet_deferred, created_at_utc
        ) VALUES (?, 'INFO', 'REVIEWED_PATTERN', ?, ?, ?, ?, 0, ?)
        """,
        (
            diagnosis["crew_id"],
            f"{diagnosis['pattern_label_en']} · reviewed by your physician",
            message,
            json.dumps(diagnosis["preventive_steps"]),
            (diagnosis["cited_article_ids"] or [None])[0],
            stamp,
        ),
    )
    return int(cursor.lastrowid)


def _promote_to_guide(conn: sqlite3.Connection, diagnosis: dict, stamp: str) -> str:
    ensure_guide_schema(conn)
    primary = get_article(conn, (diagnosis["cited_article_ids"] or [""])[0])
    article_id = f"wiki-case-{diagnosis['id']}"
    conn.execute(
        """
        INSERT OR IGNORE INTO wiki_articles (
            id, category_en, title_en, drawer_code, steps_json, escalation_en,
            source_diagnosis_id, created_at_utc, updated_at_utc, source_en
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article_id,
            PATTERN_CATEGORY.get(diagnosis["pattern_key"] or "", "Cardiorespiratory"),
            f"Validated Case: {diagnosis['pattern_label_en']}",
            primary["drawer_code"] if primary else "DRAWER B2",
            json.dumps(diagnosis["preventive_steps"]),
            # The guide is open to everyone on board: physician notes about one
            # crew member stay in the private advisory, never in the article.
            primary["escalation_en"] if primary else "Call the crew physician.",
            diagnosis["id"],
            stamp,
            stamp,
            f"Case validated by the crew physician on {stamp[:10]}.",
        ),
    )
    return article_id


class ReviewError(ValueError):
    """The finding cannot be reviewed (missing or already reviewed)."""


def review_diagnosis(conn: sqlite3.Connection, diagnosis_id: int, physician_id: str,
                     decision: str, notes: str | None = None) -> dict:
    if decision not in DECISIONS:
        raise ReviewError("Unknown decision.")
    diagnosis = get_diagnosis(conn, diagnosis_id)
    if diagnosis is None:
        raise ReviewError("Finding not found.")
    if diagnosis["validation_status"] != "PENDING_REVIEW":
        raise ReviewError("Finding already reviewed.")
    stamp = _now().strftime(TS_FORMAT)
    conn.execute(
        """
        UPDATE diagnoses SET validation_status = ?, validated_by = ?, validated_at_utc = ?,
               physician_notes_en = ?
        WHERE id = ?
        """,
        (decision, physician_id, stamp, notes, diagnosis_id),
    )
    outcome: dict = {"alert_id": None, "guide_article_id": None}
    if decision in ("APPROVED", "PROMOTED_TO_GUIDE"):
        outcome["alert_id"] = _notify_crew(conn, diagnosis, notes, stamp)
    if decision == "PROMOTED_TO_GUIDE":
        outcome["guide_article_id"] = _promote_to_guide(conn, diagnosis, stamp)
    return {**get_diagnosis(conn, diagnosis_id), **outcome}
