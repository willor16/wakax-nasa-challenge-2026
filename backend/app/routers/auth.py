"""Crew profile listing and 4-digit PIN authentication endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth_utils import create_access_token, get_current_crew, verify_pin
from app.db import open_connection

router = APIRouter(prefix="/api/v1", tags=["auth"])

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 5


class PinLoginRequest(BaseModel):
    crew_id: str = Field(..., min_length=1, max_length=32)
    pin: str = Field(..., pattern=r"^\d{4}$")


def _short_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}".upper()
    return full_name.upper()


@router.get("/crew/profiles")
def list_crew_profiles() -> list[dict]:
    """Return active crew profiles with computed readiness status for public sign-in."""
    with open_connection() as conn:
        members = conn.execute(
            """
            SELECT id, code, full_name, role, failed_attempts, locked_until_utc
            FROM crew_members
            WHERE is_active = 1
            ORDER BY code ASC
            """
        ).fetchall()

        profiles: list[dict] = []
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        for m in members:
            alerts = conn.execute(
                """
                SELECT severity
                FROM alerts
                WHERE crew_id = ? AND acknowledged_at_utc IS NULL
                """,
                (m["id"],),
            ).fetchall()
            severities = {a["severity"] for a in alerts}
            if "CRITICAL" in severities:
                readiness = "Critical"
            elif "WARNING" in severities:
                readiness = "Attention"
            else:
                readiness = "Optimal"

            locked_until = m["locked_until_utc"]
            is_locked = bool(locked_until and locked_until > now_iso)
            profiles.append(
                {
                    "id": m["id"],
                    "code": m["code"],
                    "full_name": m["full_name"],
                    "short_name": _short_name(m["full_name"]),
                    "role": m["role"],
                    "status": readiness,
                    "unread_alerts": len(alerts),
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
            SELECT id, code, full_name, role, pin_hash, is_active,
                   failed_attempts, locked_until_utc
            FROM crew_members
            WHERE id = ?
            """,
            (body.crew_id,),
        ).fetchone()

        if member is None or int(member["is_active"]) != 1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Crew member profile not found.",
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
                locked_until = (now + timedelta(minutes=LOCKOUT_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
                    detail="Too many failed PIN attempts. Profile locked for 5 minutes.",
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
            "short_name": _short_name(member["full_name"]),
            "role": member["role"],
        }
        token = create_access_token(crew_payload)
        return {
            "access_token": token,
            "token_type": "bearer",
            "crew": crew_payload,
        }


@router.get("/auth/me")
def get_authenticated_profile(claims: dict = Depends(get_current_crew)) -> dict:
    """Return the active authenticated crew member profile."""
    with open_connection() as conn:
        member = conn.execute(
            """
            SELECT id, code, full_name, role, age, sex, blood_type, height_cm
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
        data["short_name"] = _short_name(member["full_name"])
        return data
