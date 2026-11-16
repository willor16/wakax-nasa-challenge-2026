"""Sleep capture and the Sleep Architecture & Quality results."""

import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth_utils import CurrentCrew, ensure_crew_access
from app.deps import get_db_conn
from app.schemas.measurements import normalize_utc_timestamp
from app.services.sleep_service import build_sleep_monitor, create_sleep_session

router = APIRouter(prefix="/api/v1", tags=["sleep"])

DbConn = Annotated[sqlite3.Connection, Depends(get_db_conn)]
SleepPeriod = Literal["last_night", "7d", "14d", "30d"]


class SleepStageIn(BaseModel):
    stage: Literal["DEEP", "REM", "LIGHT", "AWAKE"]
    duration_min: int = Field(..., ge=1, le=600)


class SleepSessionIn(BaseModel):
    sleep_start_utc: str
    sleep_end_utc: str
    stages: list[SleepStageIn] | None = Field(default=None, max_length=80)


@router.post("/sleep/sessions", status_code=status.HTTP_201_CREATED)
def post_sleep_session(body: SleepSessionIn, conn: DbConn, claims: CurrentCrew) -> dict:
    """Log the signed-in crew member's last sleep window."""
    try:
        start = normalize_utc_timestamp(body.sleep_start_utc)
        end = normalize_utc_timestamp(body.sleep_end_utc)
        return create_sleep_session(
            conn, claims["sub"], start, end,
            [s.model_dump() for s in body.stages] if body.stages else None,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/sleep/{crew_id}")
def get_sleep_monitor(crew_id: str, conn: DbConn, claims: CurrentCrew,
                      period: Annotated[SleepPeriod, Query()] = "last_night") -> dict:
    ensure_crew_access(claims, crew_id)
    monitor = build_sleep_monitor(conn, crew_id.strip(), period=period)
    if monitor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")
    return monitor
