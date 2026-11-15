"""Notifications API (D3-02): health advisories, scheduled checks and acknowledgement.

Feeds the Notifications screen (16), opened only from the header bell.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth_utils import get_current_crew
from app.db import open_connection
from app.services.alert_engine import load_quiet_hours
from app.services.alert_rules import is_quiet_hours
from app.services.scheduled_checks import PLAN_BY_TYPE

router = APIRouter(prefix="/api/v1", tags=["alerts"])

View = Literal["all", "advisories", "checks"]
Crew = Annotated[dict, Depends(get_current_crew)]
SEVERITY_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


def _care_steps(raw: str) -> list[dict[str, str]]:
    """Steps as ``{title_en, detail_en}``; older rows stored plain sentences."""
    try:
        steps = json.loads(raw)
    except json.JSONDecodeError:
        return []
    normalized = []
    for step in steps:
        if isinstance(step, dict):
            normalized.append({
                "title_en": str(step.get("title_en", "")),
                "detail_en": str(step.get("detail_en", "")),
            })
        elif isinstance(step, str) and step.strip():
            normalized.append({"title_en": step.strip(), "detail_en": ""})
    return normalized


def _advisory(row: Any) -> dict:
    return {
        "id": row["id"],
        "kind": "ADVISORY",
        "severity": row["severity"],
        "category": row["category"],
        "title_en": row["title_en"],
        "message_en": row["message_en"],
        "care_steps": _care_steps(row["recommended_actions_json"]),
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

    advisories = [
        _advisory(r) for r in advisory_rows
        if not (resting and r["is_quiet_deferred"] and r["severity"] != "CRITICAL")
    ]
    advisories.sort(key=lambda a: (a["acknowledged_at_utc"] is not None,
                                   SEVERITY_ORDER.get(a["severity"], 9)))
    checks = [_check(r) for r in check_rows]

    open_advisories = sum(1 for a in advisories if a["acknowledged_at_utc"] is None)
    items: list[dict] = []
    if view in ("all", "advisories"):
        items.extend(advisories)
    if view in ("all", "checks"):
        items.extend(checks)
    return {
        "crew_id": crew_id,
        "view": view,
        "counts": {
            "all": open_advisories + len(checks),
            "advisories": open_advisories,
            "checks": len(checks),
        },
        "quiet_hours": {"start_utc": quiet.start_utc, "end_utc": quiet.end_utc,
                        "active": resting},
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
