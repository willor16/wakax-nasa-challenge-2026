import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth_utils import get_current_crew
from app.deps import get_db_conn
from app.schemas.vision import (
    VisionExamOut,
    VisionReviewCreatedOut,
    VisionReviewCreateIn,
    VisionStageFilter,
)
from app.services.vision_service import build_vision_exam, record_vision_review

router = APIRouter(prefix="/api/v1", tags=["vision"])

DbConn = Annotated[sqlite3.Connection, Depends(get_db_conn)]
CurrentCrew = Annotated[dict, Depends(get_current_crew)]


@router.get("/vision/{crew_id}", response_model=VisionExamOut)
def get_vision_exam_endpoint(
    crew_id: str,
    conn: DbConn,
    stage: Annotated[VisionStageFilter, Query()] = "ALL",
) -> VisionExamOut:
    exam = build_vision_exam(conn, crew_id=crew_id, stage=stage)
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crew member '{crew_id}' was not found.",
        )
    return exam


@router.post(
    "/vision/{crew_id}/review",
    response_model=VisionReviewCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
def create_vision_review_endpoint(
    crew_id: str,
    payload: VisionReviewCreateIn,
    claims: CurrentCrew,
    conn: DbConn,
) -> VisionReviewCreatedOut:
    if claims.get("role") != "PHYSICIAN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the crew physician may validate ocular findings.",
        )
    try:
        return record_vision_review(
            conn=conn,
            crew_id=crew_id,
            physician_id=str(claims["sub"]),
            payload=payload,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
