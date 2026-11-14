"""Cryptographic PIN verification and JWT session utilities."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Header, HTTPException, status

from app.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET


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


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an onboard JWT session token."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired crew session.",
        ) from exc


def get_current_crew(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """FastAPI dependency extracting the authenticated crew claims from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    token = authorization.removeprefix("Bearer ").strip()
    return decode_access_token(token)
