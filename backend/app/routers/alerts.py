"""Notifications API (D3-02): health advisories, scheduled checks and acknowledgement.

Feeds the Notifications screen (16), opened only from the header bell.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth_utils import get_current_crew
from app.db import open_connection
from app.services.alert_engine import load_quiet_hours
from app.services.alert_rules import is_quiet_hours
from app.services.crew_metrics import evaluate_crew_readiness
from app.services.guide import normalize_steps
from app.services.reference_ranges import status_label
from app.services.scheduled_checks import PLAN_BY_TYPE

router = APIRouter(prefix="/api/v1", tags=["alerts"])

View = Literal["all", "advisories", "checks"]
Crew = Annotated[dict, Depends(get_current_crew)]
SEVERITY_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


def _advisory(row: Any) -> dict:
    return {
        "id": row["id"],
        "kind": "ADVISORY",
        "severity": row["severity"],
        "category": row["category"],
        "title_en": row["title_en"],
        "message_en": row["message_en"],
        "care_steps": [
            {**step, "done_at_utc": json.loads(row["steps_done_json"] or "{}").get(str(index))}
            for index, step in enumerate(normalize_steps(row["recommended_actions_json"]))
        ],
        "guide_article_id": row["wiki_article_id"],
        "is_quiet_deferred": bool(row["is_quiet_deferred"]),
        "created_at_utc": row["created_at_utc"],
        "acknowledged_at_utc": row["acknowledged_at_utc"],
    }


def _check(row: Any) -> dict:
    plan = PLAN_BY_TYPE.get(row["check_type"])
    return {
        "id": row["id"],
        "kind": "SCHEDULED",
        "check_type": row["check_type"],
        "title_en": row["title_en"],
        "detail_en": plan.detail_en if plan else "",
        "due_at_utc": row["due_at_utc"],
        "status": row["status"],
    }


def _summary(conn, crew_id: str) -> dict:
    """One line on what is going well, shown above the care steps."""
    crew = conn.execute("SELECT full_name FROM crew_members WHERE id = ?", (crew_id,)).fetchone()
    vitals = evaluate_crew_readiness(conn, crew_id)["vitals"]
    sleep = conn.execute(
        "SELECT sleep_score FROM sleep_sessions WHERE crew_id = ? "
        "ORDER BY sleep_end_utc DESC LIMIT 1",
        (crew_id,),
    ).fetchone()
    good: list[str] = []
    if status_label("resting_hr_bpm", vitals["resting_hr_bpm"]) == "NOMINAL":
        good.append(f"heart rate ({vitals['resting_hr_bpm']:g} bpm)")
    if sleep and sleep["sleep_score"] >= 80:
        good.append(f"sleep score ({sleep['sleep_score']}/100)")
    if status_label("spo2_pct", vitals["spo2_pct"]) == "NOMINAL":
        good.append(f"oxygen ({vitals['spo2_pct']:g}%)")
    if not good:
        text = "Several readings need attention today."
    elif len(good) == 1:
        text = f"{good[0].capitalize()} remains optimal."
    else:
        text = f"{', '.join(good[:-1])} and {good[-1]} remain optimal.".capitalize()
    return {"crew_name": crew["full_name"] if crew else "", "text_en": text}


@router.get("/alerts")
def list_alerts(
    claims: Crew,
    view: Annotated[View, Query()] = "all",
    include_acknowledged: Annotated[bool, Query()] = False,
) -> dict:
    """Open advisories and pending checks for the signed-in crew member.

    Non-critical advisories deferred by Quiet Hours stay hidden while the rest
    period lasts; CRITICAL ones are always shown.
    """
    crew_id = claims["sub"]
    now = datetime.now(UTC)
    with open_connection() as conn:
        quiet = load_quiet_hours(conn)
        resting = is_quiet_hours(now, quiet)
        ack_filter = "" if include_acknowledged else "AND acknowledged_at_utc IS NULL"
        advisory_rows = conn.execute(
            f"""
            SELECT * FROM alerts
            WHERE crew_id = ? {ack_filter}
            ORDER BY created_at_utc DESC, id DESC
            """,
            (crew_id,),
        ).fetchall()
        check_rows = conn.execute(
            """
            SELECT * FROM scheduled_checks
            WHERE crew_id = ? AND status IN ('PENDING', 'DEFERRED')
            ORDER BY due_at_utc, id
            """,
            (crew_id,),
        ).fetchall()

        message_row = conn.execute(
            """SELECT id, bundle_json, delivered_at_utc FROM ground_outbox
               WHERE direction = 'INBOUND' AND packet_type = 'GROUND_DIRECTIVE'
                 AND status IN ('DELIVERED', 'ACKNOWLEDGED') AND delivered_at_utc >= ?
                 AND (crew_id IS NULL OR crew_id = ?)
               ORDER BY delivered_at_utc DESC LIMIT 1""",
            ((now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"), crew_id),
        ).fetchone()
        summary = _summary(conn, crew_id)

    advisories = [
        _advisory(r)
        for r in advisory_rows
        if not (resting and r["is_quiet_deferred"] and r["severity"] != "CRITICAL")
    ]
    advisories.sort(
        key=lambda a: (a["acknowledged_at_utc"] is not None, SEVERITY_ORDER.get(a["severity"], 9))
    )
    checks = [_check(r) for r in check_rows]

    open_advisories = sum(1 for a in advisories if a["acknowledged_at_utc"] is None)
    items: list[dict] = []
    if view in ("all", "advisories"):
        items.extend(advisories)
    if view in ("all", "checks"):
        items.extend(checks)
    messages = []
    if message_row is not None:
        bundle = json.loads(message_row["bundle_json"])
        messages.append(
            {
                "id": message_row["id"],
                "kind": "MISSION_CONTROL",
                "title_en": bundle.get("title_en", "Message from Mission Control"),
                "message_en": bundle.get("guidance_en", ""),
                "sender_en": bundle.get("sender_en", "Mission Control"),
                "created_at_utc": message_row["delivered_at_utc"],
            }
        )
    if view == "all":
        items.extend(messages)
    return {
        "summary": summary,
        "crew_id": crew_id,
        "view": view,
        "counts": {
            "all": open_advisories + len(checks) + len(messages),
            "urgent": sum(
                1
                for a in advisories
                if a["acknowledged_at_utc"] is None and a["severity"] != "INFO"
            ),
            "advisories": open_advisories,
            "checks": len(checks),
        },
        "quiet_hours": {"start_utc": quiet.start_utc, "end_utc": quiet.end_utc, "active": resting},
        "items": items,
    }


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, claims: Crew) -> dict:
    """Mark an advisory as read. Crew members confirm their own; the physician any."""
    crew_id = claims["sub"]
    with open_connection() as conn:
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if row is None or (row["crew_id"] != crew_id and claims.get("role") != "PHYSICIAN"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
        if row["acknowledged_at_utc"] is None:
            conn.execute(
                "UPDATE alerts SET acknowledged_at_utc = ?, acknowledged_by = ? WHERE id = ?",
                (datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), crew_id, alert_id),
            )
            conn.commit()
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    return _advisory(row)


@router.post("/alerts/{alert_id}/steps/{step_index}/complete")
def complete_care_step(alert_id: int, step_index: int, claims: Crew) -> dict:
    """Mark one care step of your own advisory as done (or undo it)."""
    with open_connection() as conn:
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if row is None or row["crew_id"] != claims["sub"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
        steps = normalize_steps(row["recommended_actions_json"])
        if not 0 <= step_index < len(steps):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found.")
        done = json.loads(row["steps_done_json"] or "{}")
        key = str(step_index)
        if key in done:
            done.pop(key)
        else:
            done[key] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "UPDATE alerts SET steps_done_json = ? WHERE id = ?", (json.dumps(done), alert_id)
        )
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    return _advisory(row)
