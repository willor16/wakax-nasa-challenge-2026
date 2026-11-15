import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.deps import get_db_conn
from app.schemas.profile import CrewProfileOut, MissionStage
from app.services.profile_service import build_crew_profile

router = APIRouter(prefix="/api/v1", tags=["profile"])

DbConn = Annotated[sqlite3.Connection, Depends(get_db_conn)]


@router.get("/crew/{crew_id}/profile", response_model=CrewProfileOut)
def get_crew_profile(
    conn: DbConn,
    crew_id: Annotated[str, Path(min_length=2, max_length=32)],
    stage: Annotated[MissionStage | None, Query()] = None,
) -> CrewProfileOut:
    profile = build_crew_profile(conn, crew_id.strip(), stage=stage)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active crew member '{crew_id}' was not found.",
        )
    return profile
