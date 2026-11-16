"""Mission Control link (screen 15): delayed messages, transmission log and solar weather."""

import hmac
import json
from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth_utils import (
    GROUND_SESSION_HOURS,
    CurrentCrew,
    GroundSession,
    create_ground_token,
)
from app.config import GROUND_LINK_KEY
from app.db import open_connection
from app.routers.crew import GroundCrewDirectiveIn, queue_crew_order, verify_ground_signature
from app.services import habits
from app.services.clinical_view import metric_view
from app.services.comms_service import (
    PACKET_TITLES,
    earth_latency_min,
    enqueue_packet,
    process_ground_outbox,
)
from app.services.crew_metrics import evaluate_crew_readiness
from app.services.environment import cabin_snapshot
from app.services.mission_clock import parse_iso, to_iso, utc_now

router = APIRouter(prefix="/api/v1", tags=["comms"])

ARCHIVE_AFTER = timedelta(hours=24)


class QueuePacketIn(BaseModel):
    packet_type: Literal["DAILY_SUMMARY", "CLINICAL_REPORT"] = "DAILY_SUMMARY"
    note_en: str | None = Field(default=None, max_length=280)


class InboundDirectiveIn(BaseModel):
    crew_id: str | None = Field(default=None, max_length=32)
    sender_en: str = Field(default="Flight Surgeon", min_length=2, max_length=60)
    title_en: str = Field(..., min_length=2, max_length=120)
    guidance_en: str = Field(..., min_length=4, max_length=500)


def _bundle(row) -> dict:
    try:
        return json.loads(row["bundle_json"])
    except json.JSONDecodeError:
        return {}


def _message(row, now) -> dict:
    data = _bundle(row)
    arrived = row["delivered_at_utc"] or row["deliver_after_utc"]
    if row["status"] == "ACKNOWLEDGED":
        state = "ARCHIVED" if now - parse_iso(arrived) > ARCHIVE_AFTER else "CONFIRMED"
    else:
        state = "NEW"
    return {
        "id": row["id"],
        "sender_en": data.get("sender_en") or "Mission Control",
        "title_en": data.get("title_en") or "Message from Mission Control",
        "guidance_en": data.get("guidance_en") or "",
        "crew_id": row["crew_id"],
        "received_at_utc": arrived,
        "state": state,
    }


def _log_entry(row) -> dict:
    data = _bundle(row)
    inbound = row["direction"] == "INBOUND"
    if inbound:
        state = "RECEIVED" if row["status"] in ("DELIVERED", "ACKNOWLEDGED") else "INCOMING"
        title = data.get("title_en") or ("Crew Roster Update" if row["packet_type"] == "CREW_UPDATE"
                                         else "Message from Mission Control")
        at = row["delivered_at_utc"] or row["deliver_after_utc"]
    else:
        state = {"QUEUED": "QUEUED", "IN_TRANSIT": "IN TRANSIT", "DELIVERED": "DELIVERED",
                 "ACKNOWLEDGED": "DELIVERED"}[row["status"]]
        title = data.get("title_en") or PACKET_TITLES.get(row["packet_type"], "Health Packet")
        at = row["created_at_utc"]
    return {
        "id": row["id"],
        "direction": row["direction"],
        "title_en": title,
        "state": state,
        "confirmed": row["status"] == "ACKNOWLEDGED",
        "at_utc": at,
        "deliver_after_utc": row["deliver_after_utc"],
    }


def _solar(cabin: dict | None) -> dict | None:
    if cabin is None:
        return None
    kp = cabin["kp_index"]
    if cabin["solar_event"] or (kp is not None and kp >= 5):
        label, forecast, state = "Storm conditions", \
            "Solar particle event in progress · Use the shielded shelter", "ALERT"
    elif kp is not None and kp >= 4:
        label, forecast, state = "Unsettled conditions", \
            "Elevated solar activity · Exterior work under review", "WATCH"
    else:
        label, forecast, state = "Quiet conditions", \
            "No solar particle events expected · Cabin radiation levels nominal", "QUIET"
    return {
        "kp_index": kp,
        "kp_label": label,
        "forecast_en": forecast,
        "state": state,
        "radiation_msv_day": cabin["radiation_msv_day"],
        "radiation_status": cabin["statuses"]["radiation_msv"],
        "radiation_mission_msv": cabin["radiation_mission_msv"],
        "radiation_yearly_limit_msv": cabin["radiation_yearly_limit_msv"],
        "recorded_at_utc": cabin["recorded_at_utc"],
    }


@router.get("/comms")
def get_comms_status(_claims: CurrentCrew) -> dict:
    """Messages from Mission Control, the transmission log and solar weather."""
    now = utc_now()
    with open_connection() as conn:
        process_ground_outbox(conn)
        inbound = conn.execute(
            """SELECT * FROM ground_outbox WHERE direction = 'INBOUND'
               AND packet_type = 'GROUND_DIRECTIVE' AND status IN ('DELIVERED', 'ACKNOWLEDGED')
               ORDER BY COALESCE(delivered_at_utc, deliver_after_utc) DESC LIMIT 12"""
        ).fetchall()
        log_rows = conn.execute(
            """SELECT * FROM ground_outbox
               ORDER BY COALESCE(delivered_at_utc, created_at_utc) DESC, id DESC LIMIT 12"""
        ).fetchall()
        pending = conn.execute(
            "SELECT COUNT(*) FROM ground_outbox WHERE status IN ('QUEUED', 'IN_TRANSIT')"
        ).fetchone()[0]
        latency = earth_latency_min(conn)
        cabin = cabin_snapshot(conn)
    return {
        "earth_latency_min": latency,
        "pending_packets": int(pending),
        "synchronized": int(pending) == 0,
        "messages": [_message(r, now) for r in inbound],
        "transmission_log": [_log_entry(r) for r in log_rows],
        "solar_weather": _solar(cabin),
    }


@router.post("/comms/packets", status_code=status.HTTP_201_CREATED)
def queue_outbound_packet(body: QueuePacketIn, claims: CurrentCrew) -> dict:
    """Queue a crew health summary for delayed delivery to Mission Control."""
    with open_connection() as conn:
        return enqueue_packet(conn, crew_id=claims["sub"], packet_type=body.packet_type,
                              note_en=body.note_en)


@router.post("/comms/messages/{message_id}/confirm")
def confirm_message(message_id: int, claims: CurrentCrew) -> dict:
    """Confirm that a message from Mission Control was read."""
    with open_connection() as conn:
        row = conn.execute(
            """SELECT id, status FROM ground_outbox WHERE id = ? AND direction = 'INBOUND'
               AND packet_type = 'GROUND_DIRECTIVE'""",
            (message_id,),
        ).fetchone()
        if row is None or row["status"] not in ("DELIVERED", "ACKNOWLEDGED"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found.")
        conn.execute("UPDATE ground_outbox SET status = 'ACKNOWLEDGED' WHERE id = ?", (message_id,))
    return {"id": message_id, "state": "CONFIRMED", "confirmed_by": claims["sub"]}


@router.post("/comms/directives", status_code=status.HTTP_202_ACCEPTED)
async def receive_ground_directive(
    request: Request,
    x_ground_signature: Annotated[str | None, Header()] = None,
) -> dict:
    """Signed medical guidance from Mission Control; visible on board after the signal delay."""
    raw = await request.body()
    verify_ground_signature(raw, x_ground_signature)
    try:
        body = InboundDirectiveIn.model_validate_json(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "The message is incomplete or malformed.") from exc
    return queue_directive(body)


def queue_directive(body: InboundDirectiveIn) -> dict:
    """Queue guidance from Mission Control; it reaches the crew after the signal delay."""
    now = utc_now()
    with open_connection() as conn:
        latency = earth_latency_min(conn)
        bundle = {"title_en": body.title_en.strip(), "guidance_en": body.guidance_en.strip(),
                  "sender_en": body.sender_en.strip(), "sent_at_utc": to_iso(now)}
        cursor = conn.execute(
            """INSERT INTO ground_outbox (packet_type, direction, crew_id, bundle_json,
               created_at_utc, deliver_after_utc, status)
               VALUES ('GROUND_DIRECTIVE', 'INBOUND', ?, ?, ?, ?, 'IN_TRANSIT')""",
            (body.crew_id, json.dumps(bundle), to_iso(now),
             to_iso(now + timedelta(minutes=latency))),
        )
    return {"id": int(cursor.lastrowid), "status": "IN_TRANSIT", "arrives_after_min": latency}


@router.post("/comms/flush")
def flush_outbound_queue(_claims: CurrentCrew) -> dict[str, int]:
    """Advance the link right now instead of waiting for the next scheduled pass."""
    with open_connection() as conn:
        return process_ground_outbox(conn)


# ---- Ground station console (Mission Control) -------------------------------------------
# Mission Control holds no crew PIN card: it opens the console with the pre-flight link key
# and the server signs its orders on its behalf. Everything it receives is what the crew
# sent down the link.


class GroundSessionIn(BaseModel):
    link_key: str = Field(..., min_length=8, max_length=200)


@router.post("/ground/session")
def open_ground_session(body: GroundSessionIn) -> dict:
    """Exchange the pre-flight link key for an eight-hour ground station session."""
    if not hmac.compare_digest(body.link_key.strip().encode(), GROUND_LINK_KEY.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That link key is not valid.")
    return {"access_token": create_ground_token(), "expires_in_hours": GROUND_SESSION_HOURS,
            "station_en": "Mission Control"}


def _latest(conn, crew_id: str, metric_key: str) -> float | None:
    return metric_view(conn, crew_id, metric_key)["value"]


def _crew_matrix(conn) -> list[dict]:
    day = habits.current_day(conn)
    matrix = []
    for m in conn.execute(
        """SELECT id, code, full_name, role, title_en, sex, age FROM crew_members
           WHERE is_active = 1 ORDER BY code"""
    ).fetchall():
        readiness = evaluate_crew_readiness(conn, m["id"])
        psych = conn.execute(
            """SELECT mood_score, stress_score, wellbeing_index, mood_state, recorded_at_utc
               FROM psych_tests WHERE crew_id = ? ORDER BY recorded_at_utc DESC LIMIT 1""",
            (m["id"],),
        ).fetchone()
        alerts = conn.execute(
            """SELECT SUM(severity = 'CRITICAL') AS critical, COUNT(*) AS open FROM alerts
               WHERE crew_id = ? AND acknowledged_at_utc IS NULL""",
            (m["id"],),
        ).fetchone()
        streak = habits.active_streak(habits.compliant_days(conn, m["id"]),
                                      date.fromisoformat(day))
        matrix.append({
            **dict(m),
            "status": readiness["status"],
            "readiness_score": readiness["readiness_score"],
            "vitals": readiness["vitals"],
            "psych": dict(psych) if psych else None,
            "vision": {
                "acuity_snellen": _latest(conn, m["id"], "visual_acuity_snellen"),
                "optic_sheath_right_mm": _latest(conn, m["id"], "optic_sheath_right_mm"),
            },
            "body": {
                "weight_kg": _latest(conn, m["id"], "body_weight_kg"),
                "muscle_mass_kg": _latest(conn, m["id"], "muscle_mass_kg"),
            },
            "alerts": {"open": int(alerts["open"] or 0), "critical": int(alerts["critical"] or 0)},
            "streak_days": streak,
        })
    return matrix


@router.get("/comms/ground/overview")
def ground_overview(_ground: GroundSession) -> dict:
    """Everything Mission Control has received: the crew matrix, every health packet that
    reached the ground (opened) and the orders still travelling up to the ship."""
    now = utc_now()
    with open_connection() as conn:
        process_ground_outbox(conn)
        received = conn.execute(
            """SELECT * FROM ground_outbox WHERE direction = 'OUTBOUND'
               ORDER BY created_at_utc DESC, id DESC LIMIT 40"""
        ).fetchall()
        uplink = conn.execute(
            """SELECT * FROM ground_outbox WHERE direction = 'INBOUND'
               ORDER BY created_at_utc DESC, id DESC LIMIT 20"""
        ).fetchall()
        latency = earth_latency_min(conn)
        matrix = _crew_matrix(conn)
        roster = [dict(r) for r in conn.execute(
            """SELECT id, code, full_name, role, title_en, age, sex, blood_type, height_cm,
                      is_active FROM crew_members ORDER BY code"""
        )]
    packets = []
    for r in received:
        arrived = r["status"] in ("DELIVERED", "ACKNOWLEDGED")
        packets.append({
            "id": r["id"],
            "packet_type": r["packet_type"],
            "title_en": _bundle(r).get("title_en") or PACKET_TITLES.get(r["packet_type"]),
            "state": "RECEIVED" if arrived else "IN TRANSIT",
            "sent_at_utc": r["created_at_utc"],
            "arrives_at_utc": r["delivered_at_utc"] or r["deliver_after_utc"],
            # Only what actually reached the ground can be opened.
            "bundle": _bundle(r) if arrived else None,
        })
    orders = []
    for r in uplink:
        data = _bundle(r)
        data.pop("pin_hash", None)
        travelling = r["status"] in ("QUEUED", "IN_TRANSIT")
        due = parse_iso(r["deliver_after_utc"])
        orders.append({
            "id": r["id"],
            "packet_type": r["packet_type"],
            "crew_id": r["crew_id"] or data.get("crew_id"),
            "summary_en": data.get("title_en") or (
                f"{data.get('action', 'UPDATE').title()} crew {data.get('crew_id', '')}".strip()),
            "state": "IN TRANSIT" if travelling else "ON BOARD",
            "sent_at_utc": r["created_at_utc"],
            "arrives_at_utc": r["deliver_after_utc"],
            "seconds_left": max(0, int((due - now).total_seconds())) if travelling else 0,
        })
    return {"earth_latency_min": latency, "server_utc": to_iso(now), "crew": matrix,
            "roster": roster, "packets": packets, "uplink": orders}


@router.post("/comms/ground/crew", status_code=status.HTTP_202_ACCEPTED)
def ground_crew_order(body: GroundCrewDirectiveIn, _ground: GroundSession) -> dict:
    """Add, change or deactivate a crew member from the ground (applied after the delay)."""
    return queue_crew_order(body)


@router.post("/comms/ground/directives", status_code=status.HTTP_202_ACCEPTED)
def ground_directive(body: InboundDirectiveIn, _ground: GroundSession) -> dict:
    """Send guidance to one crew member or the whole crew (arrives after the delay)."""
    return queue_directive(body)


@router.post("/comms/ground/flush")
def ground_orbital_pass(_ground: GroundSession) -> dict[str, int]:
    """Complete the orbital pass now (live demonstrations): everything travelling arrives."""
    with open_connection() as conn:
        last = conn.execute(
            "SELECT MAX(deliver_after_utc) FROM ground_outbox"
            " WHERE status IN ('QUEUED', 'IN_TRANSIT')"
        ).fetchone()[0]
        moment = max(to_iso(utc_now()), last) if last else None
        return process_ground_outbox(conn, moment)
