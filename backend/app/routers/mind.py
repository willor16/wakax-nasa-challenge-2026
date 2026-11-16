"""Psychological check-ins, reaction test sessions and the psychological profile (D3-03).

Screen 13 (``/capture/psych-sleep``) writes; screen 05 (``/profile/psychological``)
reads. Writes are always for the signed-in crew member.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth_utils import ensure_crew_access, get_current_crew
from app.db import open_connection
from app.services.mind import psych_profile, save_checkin, save_reaction_session
from app.services.mission_clock import to_iso, utc_now
from app.services.sleep_service import create_sleep_session

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
        saved["sleep_session"] = None
        if body.sleep_onset_utc and body.wake_utc:
            start, end = _sleep_window(body.sleep_onset_utc, body.wake_utc)
            try:
                saved["sleep_session"] = create_sleep_session(conn, claims["sub"], start, end)
            except ValueError as exc:
                saved["sleep_note_en"] = str(exc)
    return saved


def _sleep_window(onset: str, wake: str) -> tuple[str, str]:
    """Turn the two clock times into last night's window (wake is the latest one before now)."""
    now = utc_now()
    hour, minute = (int(part) for part in wake.split(":"))
    end = datetime(now.year, now.month, now.day, hour, minute, tzinfo=now.tzinfo)
    if end > now:
        end -= timedelta(days=1)
    hour, minute = (int(part) for part in onset.split(":"))
    start = end.replace(hour=hour, minute=minute)
    if start >= end:
        start -= timedelta(days=1)
    return to_iso(start), to_iso(end)


@router.post("/cognitive/sessions", status_code=status.HTTP_201_CREATED)
def create_reaction_session(body: ReactionSessionIn, claims: Crew) -> dict:
    """Score and store one 2-minute reaction test."""
    with open_connection() as conn:
        saved = save_reaction_session(
            conn, claims["sub"], body.reaction_times_ms, body.false_starts, body.duration_sec
        )
    return saved


@router.get("/psych/profile")
def get_psych_profile(
    claims: Crew,
    days: Annotated[int, Query(ge=1, le=60)] = 14,
    crew_id: Annotated[str | None, Query(max_length=32)] = None,
    period: Annotated[Literal["7d", "14d", "30d", "all"] | None, Query()] = None,
) -> dict:
    """Read-only psychological and reaction results for screen 05.

    Crew members see their own; the physician may open any crew member's.
    """
    target = crew_id or claims["sub"]
    ensure_crew_access(claims, target)
    with open_connection() as conn:
        if conn.execute("SELECT 1 FROM crew_members WHERE id = ?", (target,)).fetchone() is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")
        window = days if period is None else {"7d": 7, "14d": 14, "30d": 30, "all": None}[period]
        return psych_profile(conn, target, days=window)
