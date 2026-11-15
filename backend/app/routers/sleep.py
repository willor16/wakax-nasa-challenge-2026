import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.deps import get_db_conn
from app.schemas.sleep import (
    SleepMonitorOut,
    SleepPeriod,
    SleepSessionCreatedOut,
    SleepSessionCreateIn,
)
from app.services.sleep_service import build_sleep_monitor, create_sleep_session

router = APIRouter(prefix="/api/v1", tags=["sleep"])

DbConn = Annotated[sqlite3.Connection, Depends(get_db_conn)]
HTTP_422_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


@router.post(
    "/sleep/sessions",
    response_model=SleepSessionCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
def post_sleep_session(
    conn: DbConn,
    payload: SleepSessionCreateIn,
) -> SleepSessionCreatedOut:
    try:
        created = create_sleep_session(conn, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail=str(exc),
        ) from exc

    if created is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active crew member '{payload.crew_id}' was not found.",
        )
    return created


@router.get("/sleep/{crew_id}", response_model=SleepMonitorOut)
def get_crew_sleep_monitor(
    conn: DbConn,
    crew_id: Annotated[str, Path(min_length=2, max_length=32)],
    period: Annotated[SleepPeriod, Query()] = "last_night",
) -> SleepMonitorOut:
    monitor = build_sleep_monitor(conn, crew_id.strip(), period=period)
    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active crew member '{crew_id}' was not found.",
        )
    return monitor
