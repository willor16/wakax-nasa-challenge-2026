"""Crew profile results (Personal Data and Physical screens)."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth_utils import CurrentCrew, ensure_crew_access
from app.deps import get_db_conn
from app.services.profile_service import build_crew_profile

router = APIRouter(prefix="/api/v1", tags=["profile"])

DbConn = Annotated[sqlite3.Connection, Depends(get_db_conn)]


@router.get("/crew/{crew_id}/profile")
def get_crew_profile(crew_id: str, conn: DbConn, claims: CurrentCrew) -> dict:
    ensure_crew_access(claims, crew_id)
    profile = build_crew_profile(conn, crew_id.strip())
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")
    return profile
