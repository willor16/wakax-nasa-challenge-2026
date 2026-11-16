"""Crew administration, baselines, mission stage and the public Crew Overview."""

import hashlib
import hmac
import json
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.auth_utils import CurrentCrew, OperatorCrew, PhysicianCrew, ensure_crew_access, hash_pin
from app.config import GROUND_LINK_KEY
from app.db import open_connection
from app.services import habits
from app.services.crew_metrics import compute_crew_baselines, evaluate_crew_readiness
from app.services.crew_names import display_title, short_name  # noqa: F401
from app.services.environment import cabin_mode, cabin_snapshot
from app.services.mission_clock import mission_row, to_iso, utc_now
from app.services.patient_history import CATEGORIES, clinical_history, patient_list
from app.services.pilot_readiness import pilot_readiness
from app.services.reference_ranges import status_label

router = APIRouter(prefix="/api/v1", tags=["crew"])

CrewRole = Literal["ASTRONAUT", "PILOT", "OPERATOR", "PHYSICIAN"]
MissionStage = Literal["LAUNCH", "MISSION", "RETURN"]
STAGE_ORDER = ("LAUNCH", "MISSION", "RETURN")

_CREW_COLUMNS = """id, code, full_name, role, title_en, age, sex, blood_type, height_cm,
                   is_active, failed_attempts, locked_until_utc, created_at_utc, updated_at_utc"""


class CrewCreateIn(BaseModel):
    id: str = Field(..., pattern=r"^ID-\d{2,4}$")
    code: str = Field(..., min_length=3, max_length=16)
    full_name: str = Field(..., min_length=2, max_length=80)
    role: CrewRole
    title_en: str | None = Field(default=None, max_length=40)
    pin: str = Field(..., pattern=r"^\d{4}$")
    age: int | None = Field(default=None, ge=18, le=80)
    sex: Literal["F", "M", "X"] | None = None
    blood_type: str | None = Field(default=None, max_length=8)
    height_cm: float | None = Field(default=None, gt=100, lt=240)


class CrewUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=80)
    role: CrewRole | None = None
    title_en: str | None = Field(default=None, max_length=40)
    pin: str | None = Field(default=None, pattern=r"^\d{4}$")
    age: int | None = Field(default=None, ge=18, le=80)
    sex: Literal["F", "M", "X"] | None = None
    blood_type: str | None = Field(default=None, max_length=8)
    height_cm: float | None = Field(default=None, gt=100, lt=240)
    is_active: bool | None = None
    unlock_account: bool = False


class GroundCrewDirectiveIn(BaseModel):
    action: Literal["CREATE", "UPDATE", "DEACTIVATE"]
    crew_id: str = Field(..., pattern=r"^ID-\d{2,4}$")
    code: str | None = Field(default=None, min_length=3, max_length=16)
    full_name: str | None = Field(default=None, min_length=2, max_length=80)
    role: CrewRole | None = None
    pin: str | None = Field(default=None, pattern=r"^\d{4}$")
    title_en: str | None = Field(default=None, max_length=40)
    age: int | None = Field(default=None, ge=18, le=80)
    sex: Literal["F", "M", "X"] | None = None
    blood_type: str | None = Field(default=None, max_length=8)
    height_cm: float | None = Field(default=None, gt=100, lt=240)


class StageChangeIn(BaseModel):
    stage: MissionStage


def _latest_payload(conn, crew_id: str, metric_key: str):
    return conn.execute(
        """SELECT value_num, payload_json, recorded_at_utc FROM measurements
           WHERE crew_id = ? AND metric_key = ? ORDER BY recorded_at_utc DESC, id DESC LIMIT 1""",
        (crew_id, metric_key),
    ).fetchone()


def _work_shift(conn, crew_id: str) -> dict | None:
    row = _latest_payload(conn, crew_id, "work_shift_min")
    if row is None:
        return None
    payload = json.loads(row["payload_json"] or "{}")
    return {
        "mode": payload.get("mode", "IVA"),
        "minutes": int(row["value_num"]),
        "location_en": payload.get("location_en"),
        "recorded_at_utc": row["recorded_at_utc"],
    }


@router.get("/crew-overview")
def get_crew_overview() -> dict:
    """Public read-only summary: status and four key signs per crew member, plus the cabin."""
    with open_connection() as conn:
        members = conn.execute(
            "SELECT id, code, full_name, role, title_en, sex FROM crew_members "
            "WHERE is_active = 1 ORDER BY code ASC"
        ).fetchall()
        day = habits.current_day(conn)
        cards: list[dict] = []
        scores: list[int] = []
        habit_days: list[dict] = []
        for m in members:
            summary = evaluate_crew_readiness(conn, m["id"])
            scores.append(int(summary["readiness_score"]))
            vitals = summary["vitals"]
            cards.append(
                {
                    "id": m["id"],
                    "code": m["code"],
                    "full_name": m["full_name"],
                    "title_en": display_title(m),
                    # Picks the female or male anatomical figure on the card.
                    "sex": m["sex"],
                    "status": summary["status"],
                    "readiness_score": summary["readiness_score"],
                    "work_shift": _work_shift(conn, m["id"]),
                    "vitals": {
                        **vitals,
                        "resting_hr_status": status_label(
                            "resting_hr_bpm", vitals["resting_hr_bpm"]
                        ),
                        "hrv_status": status_label("hrv_rmssd_ms", vitals["hrv_rmssd_ms"]),
                        "spo2_status": status_label("spo2_pct", vitals["spo2_pct"]),
                    },
                }
            )
            habit_days.append(habits.day_habits(conn, m["id"], day))

        count = len(members)

        def habit_avg(key: str) -> int | None:
            return (
                round(sum(d["habits"][key]["pct"] for d in habit_days) / count) if count else None
            )

        sleep_target = cards[0]["vitals"]["sleep_target_min"] if cards else 420
        below_sleep = sum(1 for c in cards if (c["vitals"]["sleep_min_24h"] or 0) < sleep_target)
        hydration_logged = [d["habits"]["hydration"] for d in habit_days]
        cabin = cabin_snapshot(conn)
        optimal = sum(1 for c in cards if c["status"] == "Optimal")
        attention = any(c["status"] == "Attention" for c in cards)
        return {
            "crew_score": round(sum(scores) / count) if count else None,
            "crew_status": "Attention" if attention else "Optimal",
            "optimal_count": optimal,
            "crew_count": count,
            "cabin_mode": cabin_mode(conn),
            "habits_date_utc": day,
            "readiness": {
                "hydration_pct": habit_avg("hydration"),
                "hydration_avg_ml": round(sum((h["value"] or 0) for h in hydration_logged) / count)
                if count
                else None,
                "hydration_target_ml": round(sum(h["target"] for h in hydration_logged) / count)
                if count
                else None,
                "sleep_target_pct": round((count - below_sleep) / count * 100) if count else None,
                "sleep_below_count": below_sleep,
                "sleep_target_min": sleep_target,
                "exercise_pct": habit_avg("exercise"),
            },
            "crew": cards,
            "cabin": cabin,
        }


@router.get("/crew")
def list_all_crew(_claims: OperatorCrew) -> list[dict]:
    """All crew records, for the operator's crew administration."""
    with open_connection() as conn:
        rows = conn.execute(
            f"SELECT {_CREW_COLUMNS} FROM crew_members ORDER BY code ASC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/crew", status_code=status.HTTP_201_CREATED)
def create_crew_member(body: CrewCreateIn, _claims: OperatorCrew) -> dict:
    """Create a crew member profile (operator only)."""
    now_utc = to_iso(utc_now())
    with open_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM crew_members WHERE id = ? OR code = ?", (body.id, body.code)
        ).fetchone()
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "That crew ID or code is already in use.")
        conn.execute(
            """INSERT INTO crew_members (id, code, full_name, role, title_en, pin_hash, age, sex,
               blood_type, height_cm, is_active, created_at_utc, updated_at_utc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                body.id,
                body.code,
                body.full_name.strip(),
                body.role,
                body.title_en,
                hash_pin(body.pin),
                body.age,
                body.sex,
                body.blood_type,
                body.height_cm,
                now_utc,
                now_utc,
            ),
        )
        created = conn.execute(
            f"SELECT {_CREW_COLUMNS} FROM crew_members WHERE id = ?", (body.id,)
        ).fetchone()
    return dict(created)


def _guard_last_operator(conn, crew_id: str, new_role: str | None, new_active: bool | None) -> None:
    """Never leave the habitat without an active operator to manage accounts."""
    current = conn.execute(
        "SELECT role, is_active FROM crew_members WHERE id = ?", (crew_id,)
    ).fetchone()
    if current["role"] != "OPERATOR" or not current["is_active"]:
        return
    losing = (new_role is not None and new_role != "OPERATOR") or new_active is False
    if not losing:
        return
    others = conn.execute(
        "SELECT COUNT(*) FROM crew_members WHERE role = 'OPERATOR' AND is_active = 1 AND id != ?",
        (crew_id,),
    ).fetchone()[0]
    if others == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "At least one active operator is required. Assign another operator first.",
        )


@router.patch("/crew/{crew_id}")
def update_crew_member(crew_id: str, body: CrewUpdateIn, _claims: OperatorCrew) -> dict:
    """Edit a profile, reset the PIN, unlock or deactivate an account (operator only)."""
    with open_connection() as conn:
        existing = conn.execute("SELECT id FROM crew_members WHERE id = ?", (crew_id,)).fetchone()
        if existing is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")
        _guard_last_operator(conn, crew_id, body.role, body.is_active)

        updates: list[str] = ["updated_at_utc = ?"]
        params: list[object] = [to_iso(utc_now())]
        fields = body.model_dump(exclude_unset=True, exclude={"pin", "unlock_account", "is_active"})
        for column, value in fields.items():
            if value is not None:
                updates.append(f"{column} = ?")
                params.append(value.strip() if isinstance(value, str) else value)
        if body.pin is not None:
            updates.append("pin_hash = ?")
            params.append(hash_pin(body.pin))
        if body.is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if body.is_active else 0)
        if body.unlock_account:
            updates.extend(["failed_attempts = 0", "locked_until_utc = NULL"])
        params.append(crew_id)
        conn.execute(f"UPDATE crew_members SET {', '.join(updates)} WHERE id = ?", tuple(params))
        updated = conn.execute(
            f"SELECT {_CREW_COLUMNS} FROM crew_members WHERE id = ?", (crew_id,)
        ).fetchone()
    return dict(updated)


@router.get("/crew/{crew_id}/baselines")
def get_crew_baselines(crew_id: str, claims: CurrentCrew) -> list[dict]:
    """Pre-flight personal baselines (own record, the physician or the operator)."""
    if claims.get("role") != "OPERATOR":
        ensure_crew_access(claims, crew_id)
    with open_connection() as conn:
        rows = conn.execute(
            """SELECT b.crew_id, b.metric_key, c.display_name_en, c.unit,
                      b.mean_val, b.std_dev, b.sample_count, b.computed_at_utc
               FROM baselines AS b JOIN metric_catalog AS c ON c.metric_key = b.metric_key
               WHERE b.crew_id = ? ORDER BY c.category, b.metric_key""",
            (crew_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/crew/{crew_id}/baselines/recompute")
def recompute_crew_baselines(crew_id: str, _claims: OperatorCrew) -> dict:
    """Recompute baselines from all pre-flight (LAUNCH) measurements of a crew member."""
    with open_connection() as conn:
        exists = conn.execute("SELECT id FROM crew_members WHERE id = ?", (crew_id,)).fetchone()
        if exists is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")
        baselines = compute_crew_baselines(conn, crew_id)
    return {"crew_id": crew_id, "updated_count": len(baselines), "baselines": baselines}


@router.post("/mission/stage")
def change_mission_stage(body: StageChangeIn, _claims: OperatorCrew) -> dict:
    """Move the mission forward: LAUNCH -> MISSION -> RETURN (operator only, never backwards)."""
    with open_connection() as conn:
        mission = mission_row(conn)
        if mission is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission is not set up yet.")
        current = mission["current_stage"]
        if STAGE_ORDER.index(body.stage) != STAGE_ORDER.index(current) + 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"The mission is in the {current.title()} stage; "
                "only the next stage can be started.",
            )
        conn.execute(
            "UPDATE mission SET current_stage = ?, updated_at_utc = ? WHERE id = 1",
            (body.stage, to_iso(utc_now())),
        )
        # Closing the pre-flight stage freezes everyone's personal baselines from all of
        # their pre-flight readings; later readings are compared against them.
        frozen = 0
        if current == "LAUNCH":
            for row in conn.execute("SELECT id FROM crew_members WHERE is_active = 1").fetchall():
                frozen += len(compute_crew_baselines(conn, row["id"]))
    return {"previous_stage": current, "current_stage": body.stage, "baselines_frozen": frozen}


@router.get("/crew/patients")
def list_patients(_claims: PhysicianCrew) -> list[dict]:
    """Every active crew member with open advisories, for the physician's patient switch."""
    with open_connection() as conn:
        return patient_list(conn)


@router.get("/crew/{crew_id}/clinical-history")
def get_clinical_history(
    crew_id: str,
    _claims: PhysicianCrew,
    category: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=10, le=1000)] = 200,
) -> dict:
    """Complete clinical record of one crew member (physician only)."""
    if category is not None and category not in CATEGORIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown reading category.")
    with open_connection() as conn:
        record = clinical_history(conn, crew_id, category, limit)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")
    return record


@router.get("/crew/{crew_id}/pilot-readiness")
def get_pilot_readiness(crew_id: str, claims: CurrentCrew) -> dict:
    """Flight & Docking Readiness of the pilot (the pilot or the physician)."""
    ensure_crew_access(claims, crew_id)
    with open_connection() as conn:
        row = conn.execute("SELECT role FROM crew_members WHERE id = ?", (crew_id,)).fetchone()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")
        if row["role"] != "PILOT":
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Flight readiness is only assessed for the pilot.")
        return pilot_readiness(conn, crew_id)


def verify_ground_signature(raw_body: bytes, signature: str | None) -> None:
    """Remote orders must carry the HMAC-SHA256 of the body, made with the pre-flight key."""
    expected = hmac.new(GROUND_LINK_KEY.encode(), raw_body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature.strip().lower()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Mission Control signature is not valid.")


@router.post("/crew/ground-sync", status_code=status.HTTP_202_ACCEPTED)
async def queue_ground_crew_directive(
    request: Request,
    x_ground_signature: Annotated[str | None, Header()] = None,
) -> dict:
    """Receive a signed remote crew-management order from Mission Control.

    The order is validated and queued; it takes effect when the one-way signal
    delay has passed (applied by the transmission scheduler).
    """
    raw = await request.body()
    verify_ground_signature(raw, x_ground_signature)
    try:
        body = GroundCrewDirectiveIn.model_validate_json(raw)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "The crew order is incomplete or malformed."
        ) from exc
    return queue_crew_order(body)


def queue_crew_order(body: GroundCrewDirectiveIn) -> dict:
    """Validate a crew order from Mission Control and queue it behind the signal delay."""
    now = utc_now()
    with open_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM crew_members WHERE id = ? OR (? IS NOT NULL AND code = ?)",
            (body.crew_id, body.code, body.code),
        ).fetchone()
        if body.action == "CREATE":
            if not (body.code and body.full_name and body.role and body.pin):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "A new crew member needs a code, name, role and PIN.",
                )
            if exists:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "That crew ID or code is already in use."
                )
        elif not conn.execute(
            "SELECT 1 FROM crew_members WHERE id = ?", (body.crew_id,)
        ).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")
        if body.action != "CREATE":
            _guard_last_operator(
                conn, body.crew_id, body.role, False if body.action == "DEACTIVATE" else None
            )
        latency = int((mission_row(conn) or {"earth_latency_min": 12})["earth_latency_min"])
        bundle = body.model_dump(exclude={"pin"})
        if body.pin:
            bundle["pin_hash"] = hash_pin(body.pin)  # the PIN itself is never stored
        cursor = conn.execute(
            """INSERT INTO ground_outbox (packet_type, direction, crew_id, bundle_json,
               created_at_utc, deliver_after_utc, status)
               VALUES ('CREW_UPDATE', 'INBOUND', ?, ?, ?, ?, 'IN_TRANSIT')""",
            (
                body.crew_id if body.action != "CREATE" else None,
                json.dumps(bundle),
                to_iso(now),
                to_iso(now + timedelta(minutes=latency)),
            ),
        )
    return {
        "status": "queued",
        "packet_id": int(cursor.lastrowid),
        "action": body.action,
        "crew_id": body.crew_id,
        "applies_after_min": latency,
    }
