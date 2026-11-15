"""Assisted findings and physician review API (D3-04, D3-05)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth_utils import get_current_crew
from app.db import open_connection
from app.services.diagnosis import (
    ReviewError,
    list_diagnoses,
    review_diagnosis,
    scan_all,
    scan_crew_member,
)

router = APIRouter(prefix="/api/v1", tags=["diagnosis"])

Crew = Annotated[dict, Depends(get_current_crew)]
Status = Literal["PENDING_REVIEW", "APPROVED", "REJECTED", "PROMOTED_TO_GUIDE"]


class ScanIn(BaseModel):
    crew_id: str | None = Field(default=None, max_length=16)


class ReviewIn(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "PROMOTED_TO_GUIDE"]
    notes_en: str | None = Field(default=None, max_length=500)


def _require_physician(claims: dict) -> None:
    if claims.get("role") != "PHYSICIAN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only the crew physician can review findings.")


@router.post("/diagnosis/anomalies")
def scan_for_anomalies(body: ScanIn, claims: Crew) -> dict:
    """Scan one crew member (yourself; the physician may scan anyone)."""
    crew_id = body.crew_id or claims["sub"]
    if crew_id != claims["sub"]:
        _require_physician(claims)
    with open_connection() as conn:
        if conn.execute("SELECT 1 FROM crew_members WHERE id = ?", (crew_id,)).fetchone() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crew not found.")
        result = scan_crew_member(conn, crew_id)
        conn.commit()
    return result


@router.get("/diagnosis")
def get_diagnoses(claims: Crew, status_filter: Annotated[Status | None, Query(alias="status")]
                  = None) -> dict:
    with open_connection() as conn:
        items = list_diagnoses(conn, viewer_id=claims["sub"], viewer_role=claims.get("role", ""),
                               status=status_filter)
    return {"items": items, "pending": sum(i["validation_status"] == "PENDING_REVIEW"
                                           for i in items)}


@router.post("/diagnosis/{diagnosis_id}/review")
def review(diagnosis_id: int, body: ReviewIn, claims: Crew) -> dict:
    _require_physician(claims)
    with open_connection() as conn:
        try:
            result = review_diagnosis(conn, diagnosis_id, claims["sub"], body.decision,
                                      body.notes_en)
        except ReviewError as exc:
            code = (status.HTTP_404_NOT_FOUND if "not found" in str(exc)
                    else status.HTTP_409_CONFLICT)
            raise HTTPException(status_code=code, detail=str(exc)) from exc
        conn.commit()
    return result


def run_anomaly_scan_tick() -> None:
    """APScheduler job: scan the whole crew."""
    with open_connection() as conn:
        scan_all(conn)
        conn.commit()
