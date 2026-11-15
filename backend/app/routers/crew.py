"""Crew administration, baseline calculation, and public Crew Overview endpoints."""

import json
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth_utils import hash_pin, require_operator
from app.db import open_connection
from app.services.crew_metrics import compute_crew_baselines, evaluate_crew_readiness

router = APIRouter(prefix="/api/v1", tags=["crew"])

CrewRole = Literal["ASTRONAUT", "PILOT", "OPERATOR", "PHYSICIAN"]


class CrewCreateIn(BaseModel):
    id: str = Field(..., pattern=r"^ID-\d{2,4}$")
    code: str = Field(..., min_length=3, max_length=16)
    full_name: str = Field(..., min_length=2, max_length=80)
    role: CrewRole
    pin: str = Field(..., pattern=r"^\d{4}$")
    age: int | None = Field(default=None, ge=18, le=80)
    sex: Literal["F", "M", "X"] | None = None
    blood_type: str | None = Field(default=None, max_length=8)
    height_cm: float | None = Field(default=None, gt=100, lt=240)


class CrewUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=80)
    role: CrewRole | None = None
    pin: str | None = Field(default=None, pattern=r"^\d{4}$")
    age: int | None = Field(default=None, ge=18, le=80)
    sex: Literal["F", "M", "X"] | None = None
    blood_type: str | None = Field(default=None, max_length=8)
    height_cm: float | None = Field(default=None, gt=100, lt=240)
    is_active: bool | None = None
    unlock_account: bool = False


class GroundCrewDirectiveIn(BaseModel):
    action: Literal["CREATE", "UPDATE", "DEACTIVATE"]
    crew_id: str = Field(..., min_length=1, max_length=32)
    code: str | None = None
    full_name: str | None = None
    role: CrewRole | None = None
    pin: str | None = Field(default=None, pattern=r"^\d{4}$")


def _short_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}".upper()
    return full_name.upper()


@router.get("/crew-overview")
def get_crew_overview() -> dict:
    """Return read-only public Crew Overview readiness, vital snapshot, and cabin metrics."""
    with open_connection() as conn:
        members = conn.execute(
            """
            SELECT id, code, full_name, role
            FROM crew_members
            WHERE is_active = 1
            ORDER BY code ASC
            """
        ).fetchall()

        crew_cards: list[dict] = []
        scores: list[int] = []
        critical_any = False

        for m in members:
            summary = evaluate_crew_readiness(conn, m["id"])
            scores.append(int(summary["readiness_score"]))
            if summary["status"] == "Critical":
                critical_any = True
            crew_cards.append(
                {
                    "id": m["id"],
                    "code": m["code"],
                    "full_name": m["full_name"],
                    "short_name": _short_name(m["full_name"]),
                    "role": m["role"],
                    **summary,
                }
            )

        cabin_row = conn.execute(
            """
            SELECT co2_ppm, noise_dba, temp_c, humidity_pct,
                   radiation_msv, solar_event_flag, recorded_at_utc
            FROM environment_readings
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        cabin = dict(cabin_row) if cabin_row else None
        if cabin and float(cabin["co2_ppm"]) >= 4000.0:
            critical_any = True

        crew_score = round(sum(scores) / len(scores)) if scores else 0
        return {
            "crew_score": crew_score,
            "crew_status": "Critical" if critical_any else ("Attention" if crew_score < 82 else "Optimal"),
            "cabin_mode": "critical" if critical_any else "nominal",
            "crew": crew_cards,
            "cabin": cabin,
        }


@router.get("/crew")
def list_all_crew(_claims: dict = Depends(require_operator)) -> list[dict]:
    """List all crew records for local Operator administration."""
    with open_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, code, full_name, role, age, sex, blood_type, height_cm,
                   is_active, failed_attempts, locked_until_utc, created_at_utc, updated_at_utc
            FROM crew_members
            ORDER BY code ASC
            """
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/crew", status_code=status.HTTP_201_CREATED)
def create_crew_member(
    body: CrewCreateIn,
    _claims: dict = Depends(require_operator),
) -> dict:
    """Create a new crew member profile (Operator only)."""
    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM crew_members WHERE id = ? OR code = ?",
            (body.id, body.code),
        ).fetchone()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Crew ID or code already exists.",
            )

        conn.execute(
            """
            INSERT INTO crew_members (
                id, code, full_name, role, pin_hash, age, sex, blood_type,
                height_cm, is_active, created_at_utc, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                body.id,
                body.code,
                body.full_name.strip(),
                body.role,
                hash_pin(body.pin),
                body.age,
                body.sex,
                body.blood_type,
                body.height_cm,
                now_utc,
                now_utc,
            ),
        )
        conn.commit()
        created = conn.execute(
            """
            SELECT id, code, full_name, role, age, sex, blood_type, height_cm,
                   is_active, created_at_utc, updated_at_utc
            FROM crew_members
            WHERE id = ?
            """,
            (body.id,),
        ).fetchone()
    return dict(created)


@router.patch("/crew/{crew_id}")
def update_crew_member(
    crew_id: str,
    body: CrewUpdateIn,
    _claims: dict = Depends(require_operator),
) -> dict:
    """Update crew profile fields, reset PIN, or toggle active status (Operator only)."""
    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open_connection() as conn:
        existing = conn.execute("SELECT * FROM crew_members WHERE id = ?", (crew_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crew member not found.")

        updates: list[str] = ["updated_at_utc = ?"]
        params: list[object] = [now_utc]

        if body.full_name is not None:
            updates.append("full_name = ?")
            params.append(body.full_name.strip())
        if body.role is not None:
            updates.append("role = ?")
            params.append(body.role)
        if body.pin is not None:
            updates.append("pin_hash = ?")
            params.append(hash_pin(body.pin))
        if body.age is not None:
            updates.append("age = ?")
            params.append(body.age)
        if body.sex is not None:
            updates.append("sex = ?")
            params.append(body.sex)
        if body.blood_type is not None:
            updates.append("blood_type = ?")
            params.append(body.blood_type)
        if body.height_cm is not None:
            updates.append("height_cm = ?")
            params.append(body.height_cm)
        if body.is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if body.is_active else 0)
        if body.unlock_account:
            updates.append("failed_attempts = 0")
            updates.append("locked_until_utc = NULL")

        params.append(crew_id)
        conn.execute(f"UPDATE crew_members SET {', '.join(updates)} WHERE id = ?", tuple(params))
        conn.commit()

        updated = conn.execute(
            """
            SELECT id, code, full_name, role, age, sex, blood_type, height_cm,
                   is_active, failed_attempts, locked_until_utc, updated_at_utc
            FROM crew_members
            WHERE id = ?
            """,
            (crew_id,),
        ).fetchone()
    return dict(updated)


@router.get("/crew/{crew_id}/baselines")
def get_crew_baselines(crew_id: str) -> list[dict]:
    """Return computed pre-mission baselines for a crew member."""
    with open_connection() as conn:
        rows = conn.execute(
            """
            SELECT b.crew_id, b.metric_key, c.display_name_en, c.unit,
                   b.mean_val, b.std_dev, b.sample_count, b.computed_at_utc
            FROM baselines AS b
            JOIN metric_catalog AS c ON c.metric_key = b.metric_key
            WHERE b.crew_id = ?
            ORDER BY b.metric_key ASC
            """,
            (crew_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/crew/{crew_id}/baselines/recompute")
def recompute_crew_baselines(
    crew_id: str,
    _claims: dict = Depends(require_operator),
) -> dict:
    """Recompute baselines from all LAUNCH measurements for a crew member."""
    with open_connection() as conn:
        exists = conn.execute("SELECT id FROM crew_members WHERE id = ?", (crew_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crew member not found.")
        baselines = compute_crew_baselines(conn, crew_id)
        conn.commit()
    return {"crew_id": crew_id, "updated_count": len(baselines), "baselines": baselines}


@router.post("/crew/ground-sync", status_code=status.HTTP_202_ACCEPTED)
def apply_ground_crew_directive(body: GroundCrewDirectiveIn) -> dict:
    """Apply an asynchronous ground-control crew management directive and log in outbox."""
    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open_connection() as conn:
        if body.action == "CREATE":
            if not body.code or not body.full_name or not body.role or not body.pin:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="CREATE directive requires code, full_name, role, and pin.",
                )
            conn.execute(
                """
                INSERT OR IGNORE INTO crew_members (
                    id, code, full_name, role, pin_hash, is_active, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (body.crew_id, body.code, body.full_name, body.role, hash_pin(body.pin), now_utc, now_utc),
            )
        elif body.action == "DEACTIVATE":
            conn.execute(
                "UPDATE crew_members SET is_active = 0, updated_at_utc = ? WHERE id = ?",
                (now_utc, body.crew_id),
            )
        elif body.action == "UPDATE":
            if body.full_name:
                conn.execute(
                    "UPDATE crew_members SET full_name = ?, updated_at_utc = ? WHERE id = ?",
                    (body.full_name, now_utc, body.crew_id),
                )
            if body.role:
                conn.execute(
                    "UPDATE crew_members SET role = ?, updated_at_utc = ? WHERE id = ?",
                    (body.role, now_utc, body.crew_id),
                )

        conn.execute(
            """
            INSERT INTO ground_outbox (
                packet_type, direction, crew_id, bundle_json,
                created_at_utc, deliver_after_utc, delivered_at_utc, status
            ) VALUES ('CREW_UPDATE', 'INBOUND', ?, ?, ?, ?, ?, 'ACKNOWLEDGED')
            """,
            (body.crew_id, json.dumps(body.model_dump(exclude={"pin"})), now_utc, now_utc, now_utc),
        )
        conn.commit()
    return {"status": "applied", "action": body.action, "crew_id": body.crew_id}
