"""Psychological check-ins, reaction test sessions and the psychological profile (D3-03).

Screen 13 (``/capture/psych-sleep``) writes; screen 05 (``/profile/psychological``)
reads. Every call is for the signed-in crew member.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.auth_utils import get_current_crew
from app.db import open_connection
from app.services.mind import psych_profile, save_checkin, save_reaction_session

router = APIRouter(prefix="/api/v1", tags=["mind"])

Crew = Annotated[dict, Depends(get_current_crew)]
Scale = Annotated[int, Field(ge=1, le=5)]
ClockTime = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


class CheckinIn(BaseModel):
    mood_state: Literal["CALM", "FOCUSED", "TIRED", "STRESSED"] | None = None
    mood: Scale
    stress: Scale
    isolation: Scale
    motivation: Scale
    sleep_onset_utc: ClockTime | None = None
    wake_utc: ClockTime | None = None


class ReactionSessionIn(BaseModel):
    reaction_times_ms: list[Annotated[float, Field(ge=0, le=10000)] | None] = Field(
        ..., min_length=1, max_length=300
    )
    false_starts: int = Field(default=0, ge=0, le=300)
    duration_sec: int = Field(default=120, ge=10, le=600)


@router.post("/psych/checkins", status_code=status.HTTP_201_CREATED)
def create_checkin(body: CheckinIn, claims: Crew) -> dict:
    """Store today's behavioral check-in and reported sleep window."""
    with open_connection() as conn:
        saved = save_checkin(
            conn,
            claims["sub"],
            mood_state=body.mood_state,
            mood=body.mood,
            stress=body.stress,
            isolation=body.isolation,
            motivation=body.motivation,
            sleep_onset_utc=body.sleep_onset_utc,
            wake_utc=body.wake_utc,
        )
        conn.commit()
    return saved


@router.post("/cognitive/sessions", status_code=status.HTTP_201_CREATED)
def create_reaction_session(body: ReactionSessionIn, claims: Crew) -> dict:
    """Score and store one 2-minute reaction test."""
    with open_connection() as conn:
        saved = save_reaction_session(
            conn, claims["sub"], body.reaction_times_ms, body.false_starts, body.duration_sec
        )
        conn.commit()
    return saved


@router.get("/psych/profile")
def get_psych_profile(
    claims: Crew, days: Annotated[int, Query(ge=1, le=60)] = 14
) -> dict:
    """Read-only psychological and reaction results for screen 05."""
    with open_connection() as conn:
        return psych_profile(conn, claims["sub"], days=days)
