"""Crew profile listing and 4-digit PIN authentication endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.auth_utils import (
    CurrentCrew,
    create_access_token,
    create_stream_token,
    verify_pin,
)
from app.db import open_connection
from app.services.crew_metrics import evaluate_crew_readiness
from app.services.crew_names import display_title, short_name

router = APIRouter(prefix="/api/v1", tags=["auth"])

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 5


class PinLoginRequest(BaseModel):
    crew_id: str = Field(..., min_length=1, max_length=32)
    pin: str = Field(..., pattern=r"^\d{4}$")


@router.get("/crew/profiles")
def list_crew_profiles() -> list[dict]:
    """Active crew profiles with their overall health status, for the public sign-in screen."""
    with open_connection() as conn:
        members = conn.execute(
            """
            SELECT id, code, full_name, role, title_en, failed_attempts, locked_until_utc
            FROM crew_members
            WHERE is_active = 1
            ORDER BY code ASC
            """
        ).fetchall()
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        profiles: list[dict] = []
        for m in members:
            readiness = evaluate_crew_readiness(conn, m["id"])
            locked_until = m["locked_until_utc"]
            is_locked = bool(locked_until and locked_until > now_iso)
            profiles.append(
                {
                    "id": m["id"],
                    "code": m["code"],
                    "full_name": m["full_name"],
                    "short_name": short_name(m["full_name"]),
                    "role": m["role"],
                    "title_en": display_title(m),
                    "status": readiness["status"],
                    "is_locked": is_locked,
                    "locked_until_utc": locked_until if is_locked else None,
                }
            )
    return profiles


@router.post("/auth/login")
def login_with_pin(body: PinLoginRequest) -> dict:
    """Authenticate a crew member using their 4-digit PIN and issue a session token."""
    now = datetime.now(UTC)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    with open_connection() as conn:
        member = conn.execute(
            """
            SELECT id, code, full_name, role, title_en, sex, pin_hash, is_active,
                   failed_attempts, locked_until_utc
            FROM crew_members
            WHERE id = ?
            """,
            (body.crew_id,),
        ).fetchone()

        if member is None or int(member["is_active"]) != 1:
            # Same answer as a wrong PIN, so the reply never reveals which profiles exist.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect PIN.",
            )

        if member["locked_until_utc"] and member["locked_until_utc"] > now_iso:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Profile temporarily locked due to repeated PIN attempts.",
            )

        if not verify_pin(body.pin, member["pin_hash"]):
            attempts = int(member["failed_attempts"]) + 1
            locked_until = None
            if attempts >= MAX_FAILED_ATTEMPTS:
                locked_until = (now + timedelta(minutes=LOCKOUT_MINUTES)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            conn.execute(
                """
                UPDATE crew_members
                SET failed_attempts = ?, locked_until_utc = ?, updated_at_utc = ?
                WHERE id = ?
                """,
                (attempts, locked_until, now_iso, member["id"]),
            )
            conn.commit()
            if locked_until is not None:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Too many incorrect PIN attempts. Profile locked for 5 minutes.",
                )
            remaining = MAX_FAILED_ATTEMPTS - attempts
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Incorrect PIN. {remaining} attempts remaining.",
            )

        conn.execute(
            """
            UPDATE crew_members
            SET failed_attempts = 0, locked_until_utc = NULL, updated_at_utc = ?
            WHERE id = ?
            """,
            (now_iso, member["id"]),
        )
        conn.commit()

        crew_payload = {
            "id": member["id"],
            "code": member["code"],
            "full_name": member["full_name"],
            "short_name": short_name(member["full_name"]),
            "role": member["role"],
            "title_en": display_title(member),
            # Lets the screens show normal ranges calibrated to the crew member's physiology.
            "sex": member["sex"],
        }
        token = create_access_token(crew_payload)
        return {
            "access_token": token,
            "token_type": "bearer",
            "crew": crew_payload,
        }


@router.get("/auth/me")
def get_authenticated_profile(claims: CurrentCrew) -> dict:
    """Return the active authenticated crew member profile."""
    with open_connection() as conn:
        member = conn.execute(
            """
            SELECT id, code, full_name, role, title_en, age, sex, blood_type, height_cm
            FROM crew_members
            WHERE id = ? AND is_active = 1
            """,
            (claims["sub"],),
        ).fetchone()
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Authenticated crew member not found.",
            )
        data = dict(member)
        data["short_name"] = short_name(member["full_name"])
        data["title_en"] = display_title(member)
        return data


@router.post("/auth/stream-token")
def issue_stream_token(claims: CurrentCrew) -> dict:
    """Short-lived pass for the live vitals stream (browsers cannot send headers on streams)."""
    return {"stream_token": create_stream_token(claims), "expires_in_sec": 60}
