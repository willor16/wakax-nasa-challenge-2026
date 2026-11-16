"""Psychological check-ins, reaction test sessions and the psychological profile (D3-03).

Screen 13 (``/capture/psych-sleep``) writes; screen 05 (``/profile/psychological``)
reads. Writes are always for the signed-in crew member.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator

from app.auth_utils import ensure_crew_access, get_current_crew
from app.db import open_connection
from app.services.mind import (
    psych_profile,
    save_astrocow_session,
    save_behavioral_matrix,
    save_checkin,
    save_neurofit_session,
    save_reaction_session,
)
from app.services.mission_clock import to_iso, utc_now
from app.services.sleep_service import create_sleep_session

router = APIRouter(prefix="/api/v1", tags=["mind"])

Crew = Annotated[dict, Depends(get_current_crew)]
Scale = Annotated[int, Field(ge=1, le=5)]
MatrixRating = Annotated[int, Field(ge=0, le=4)]
ClockTime = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


class CheckinIn(BaseModel):
    assessment_type: Literal["DAILY_CHECKIN", "BEHAVIORAL_MATRIX_20"] = "DAILY_CHECKIN"
    mood_state: Literal["CALM", "FOCUSED", "TIRED", "STRESSED"] | None = None
    mood: Scale | None = None
    stress: Scale | None = None
    isolation: Scale | None = None
    motivation: Scale | None = None
    item_responses: list[MatrixRating] | None = Field(default=None, min_length=20, max_length=20)
    sleep_onset_utc: ClockTime | None = None
    wake_utc: ClockTime | None = None

    @model_validator(mode="after")
    def validate_mode(self) -> CheckinIn:
        if self.assessment_type == "BEHAVIORAL_MATRIX_20":
            if self.item_responses is None or len(self.item_responses) != 20:
                raise ValueError("item_responses with 20 ratings (0-4) is required.")
            return self
        if any(v is None for v in (self.mood, self.stress, self.isolation, self.motivation)):
            raise ValueError("mood, stress, isolation and motivation are required.")
        return self


class AstroCowIn(BaseModel):
    score: int = Field(default=0, ge=0, le=100000)
    high_score: int = Field(default=0, ge=0, le=100000)
    difficulty_level: int = Field(default=1, ge=1, le=10)
    duration_sec: int = Field(default=10, ge=1, le=1800)
    mean_reaction_ms: float | None = Field(default=None, ge=0, le=20000)
    rt_variability_ms: float | None = Field(default=None, ge=0, le=20000)
    recovery_time_sec: float | None = Field(default=None, ge=0, le=120)
    errors_after_change: int = Field(default=0, ge=0, le=1000)
    omitted_responses: int = Field(default=0, ge=0, le=1000)
    precision_pct: float | None = Field(default=None, ge=0, le=100)
    collisions: int = Field(default=0, ge=0, le=500)
    reticle_hits: int = Field(default=0, ge=0, le=1000)
    reticle_total: int = Field(default=0, ge=0, le=1000)
    reaction_times_ms: list[float] = Field(default_factory=list, max_length=500)
    recovery_times_sec: list[float] = Field(default_factory=list, max_length=500)
    performance_by_minute: list[dict[str, Any]] = Field(default_factory=list, max_length=60)


class NeuroFitStageIn(BaseModel):
    key: Literal["sequence", "bee", "explorer", "scan"]
    title: str = Field(max_length=80)
    cabCode: str = Field(max_length=24)
    cabName: str = Field(max_length=80)
    score: int = Field(default=0, ge=0, le=100000)
    accuracy: float = Field(default=0.0, ge=0, le=100)
    correct_attempts: int = Field(default=0, ge=0, le=1000)
    error_attempts: int = Field(default=0, ge=0, le=1000)
    total_attempts: int = Field(default=0, ge=0, le=1000)
    avg_reaction_ms: float = Field(default=0.0, ge=0, le=30000)
    level_reached: int = Field(default=1, ge=1, le=50)
    duration_sec: int = Field(default=1, ge=1, le=600)


class NeuroFitIn(BaseModel):
    copilot_id: str = Field(default="tamalito", max_length=32)
    duration_sec: int = Field(default=90, ge=1, le=1800)
    total_score: int = Field(default=0, ge=0, le=200000)
    ecg_index: int = Field(default=400, ge=0, le=1000)
    stages: list[NeuroFitStageIn] = Field(min_length=1, max_length=8)
    cab_metrics: dict[str, Any] = Field(default_factory=dict)
    diagnostic: dict[str, Any] = Field(default_factory=dict)


class ReactionSessionIn(BaseModel):
    test_type: Literal["REACTION_ARENA", "ASTROCOW_SIM", "NEUROFIT_LAB"] = "REACTION_ARENA"
    reaction_times_ms: list[Annotated[float, Field(ge=0, le=10000)] | None] | None = Field(
        default=None, min_length=1, max_length=300
    )
    false_starts: int = Field(default=0, ge=0, le=300)
    duration_sec: int = Field(default=120, ge=1, le=1800)
    astrocow: AstroCowIn | None = None
    neurofit: NeuroFitIn | None = None

    @model_validator(mode="after")
    def validate_session(self) -> ReactionSessionIn:
        if self.test_type == "REACTION_ARENA" and not self.reaction_times_ms:
            raise ValueError("reaction_times_ms is required for REACTION_ARENA.")
        if self.test_type == "ASTROCOW_SIM" and self.astrocow is None:
            raise ValueError("astrocow payload is required for ASTROCOW_SIM.")
        if self.test_type == "NEUROFIT_LAB" and self.neurofit is None:
            raise ValueError("neurofit payload is required for NEUROFIT_LAB.")
        return self


@router.post("/psych/checkins", status_code=status.HTTP_201_CREATED)
def create_checkin(body: CheckinIn, claims: Crew) -> dict:
    """Store today's behavioral check-in or 20-item matrix and reported sleep window."""
    with open_connection() as conn:
        if body.assessment_type == "BEHAVIORAL_MATRIX_20":
            assert body.item_responses is not None
            saved = save_behavioral_matrix(
                conn,
                claims["sub"],
                body.item_responses,
                mood_state=body.mood_state,
                sleep_onset_utc=body.sleep_onset_utc,
                wake_utc=body.wake_utc,
            )
        else:
            saved = save_checkin(
                conn,
                claims["sub"],
                mood_state=body.mood_state,
                mood=body.mood or 3,
                stress=body.stress or 3,
                isolation=body.isolation or 3,
                motivation=body.motivation or 3,
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
    """Score and store one reaction, AstroCow sensorimotor, or NeuroFit cognitive session."""
    with open_connection() as conn:
        if body.test_type == "ASTROCOW_SIM":
            assert body.astrocow is not None
            return save_astrocow_session(conn, claims["sub"], body.astrocow.model_dump())
        if body.test_type == "NEUROFIT_LAB":
            assert body.neurofit is not None
            return save_neurofit_session(conn, claims["sub"], body.neurofit.model_dump())
        assert body.reaction_times_ms is not None
        return save_reaction_session(
            conn, claims["sub"], body.reaction_times_ms, body.false_starts, body.duration_sec
        )


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
