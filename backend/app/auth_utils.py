"""Cryptographic PIN verification, hashing, and JWT session utilities."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET

STREAM_SCOPE = "stream"


def hash_pin(pin: str) -> str:
    """Hash a 4-digit PIN using Argon2id (with stdlib scrypt fallback if unbundled)."""
    try:
        from argon2 import PasswordHasher

        return PasswordHasher().hash(pin)
    except ImportError:
        salt = secrets.token_hex(16)
        digest = hashlib.scrypt(pin.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1)
        return f"scrypt${salt}${digest.hex()}"


def verify_pin(pin: str, stored_hash: str) -> bool:
    """Verify a 4-digit PIN against an Argon2id or scrypt hash."""
    if stored_hash.startswith("$argon2"):
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError

        try:
            return PasswordHasher().verify(stored_hash, pin)
        except VerifyMismatchError:
            return False

    if stored_hash.startswith("scrypt$"):
        parts = stored_hash.split("$", 2)
        if len(parts) != 3:
            return False
        _, salt, expected_hex = parts
        digest = hashlib.scrypt(pin.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1)
        return hmac.compare_digest(digest.hex(), expected_hex)

    return False


def create_access_token(crew: dict[str, Any]) -> str:
    """Issue a signed JWT session token for an authenticated crew member."""
    now = datetime.now(UTC)
    payload = {
        "sub": crew["id"],
        "code": crew["code"],
        "role": crew["role"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_stream_token(claims: dict[str, Any]) -> str:
    """One-minute pass that only opens the live vitals stream of the same crew member."""
    now = datetime.now(UTC)
    payload = {
        "sub": claims["sub"],
        "role": claims["role"],
        "scope": STREAM_SCOPE,
        "exp": int((now + timedelta(seconds=60)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, scope: str | None = None) -> dict[str, Any]:
    """Decode and validate an onboard session token (stream passes only fit streams)."""
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has ended. Please sign in again.",
        ) from exc
    if claims.get("scope") != scope:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has ended. Please sign in again.",
        )
    return claims


def _claims_from_header(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in with your crew PIN.",
        )
    token = authorization.removeprefix("Bearer ").strip()
    return decode_access_token(token)


def verify_session_claims(claims: dict[str, Any]) -> dict[str, Any]:
    """Reject sessions of deactivated crew or whose role changed since sign-in."""
    from app.deps import open_request_connection

    with open_request_connection() as conn:
        row = conn.execute(
            "SELECT role, is_active FROM crew_members WHERE id = ?", (claims.get("sub"),)
        ).fetchone()
    if row is None or not row["is_active"] or row["role"] != claims.get("role"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has ended. Please sign in again.",
        )
    return claims


def get_current_crew(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """FastAPI dependency returning the claims of the signed-in crew member."""
    return verify_session_claims(_claims_from_header(authorization))


def require_operator(
    claims: Annotated[dict[str, Any], Depends(get_current_crew)],
) -> dict[str, Any]:
    """Ensure the authenticated crew member holds the OPERATOR role for user admin."""
    if claims.get("role") != "OPERATOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the crew operator can manage crew accounts.",
        )
    return claims


def require_physician(
    claims: Annotated[dict[str, Any], Depends(get_current_crew)],
) -> dict[str, Any]:
    if claims.get("role") != "PHYSICIAN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the crew physician can do this.",
        )
    return claims


def ensure_crew_access(claims: dict[str, Any], crew_id: str) -> None:
    """Crew members see their own records; the physician sees everyone's."""
    if claims.get("sub") != crew_id and claims.get("role") != "PHYSICIAN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only open your own health records.",
        )


CurrentCrew = Annotated[dict[str, Any], Depends(get_current_crew)]
OperatorCrew = Annotated[dict[str, Any], Depends(require_operator)]
PhysicianCrew = Annotated[dict[str, Any], Depends(require_physician)]


# ---- Mission Control (ground station console) ------------------------------------------
GROUND_SCOPE = "ground"
GROUND_SESSION_HOURS = 8


def create_ground_token() -> str:
    """Session of the ground station console, granted for the pre-flight link key. It never
    works as a crew session, and crew sessions never open the console."""
    now = datetime.now(UTC)
    payload = {
        "sub": "GROUND",
        "role": "GROUND_CONTROL",
        "scope": GROUND_SCOPE,
        "exp": int((now + timedelta(hours=GROUND_SESSION_HOURS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_ground_session(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Open the ground station with the link key.")
    try:
        return decode_access_token(authorization.removeprefix("Bearer ").strip(), GROUND_SCOPE)
    except HTTPException as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "The ground station session has ended. Enter the link key again.",
        ) from exc


GroundSession = Annotated[dict[str, Any], Depends(get_ground_session)]
