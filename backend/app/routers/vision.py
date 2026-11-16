"""Vision & ocular exam results and physician review."""

import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth_utils import CurrentCrew, PhysicianCrew, ensure_crew_access
from app.deps import get_db_conn
from app.services.vision_service import build_vision_exam, record_vision_review

router = APIRouter(prefix="/api/v1", tags=["vision"])

DbConn = Annotated[sqlite3.Connection, Depends(get_db_conn)]


class VisionReviewIn(BaseModel):
    decision: Literal["APPROVED", "REJECTED"] = "APPROVED"
    notes_en: str | None = Field(default=None, max_length=500)


@router.get("/vision/{crew_id}")
def get_vision_exam(crew_id: str, conn: DbConn, claims: CurrentCrew) -> dict:
    ensure_crew_access(claims, crew_id)
    exam = build_vision_exam(conn, crew_id)
    if exam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")
    return exam


@router.post("/vision/{crew_id}/review", status_code=status.HTTP_201_CREATED)
def create_vision_review(crew_id: str, body: VisionReviewIn, claims: PhysicianCrew,
                         conn: DbConn) -> dict:
    if claims["sub"] == crew_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Your own exam must be reviewed by the Mission Control flight surgeon.",
        )
    try:
        return record_vision_review(conn, crew_id, str(claims["sub"]), body.decision,
                                    body.notes_en)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
