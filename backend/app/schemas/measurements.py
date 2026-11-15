import math
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MissionStage = Literal["LAUNCH", "MISSION", "RETURN"]
MeasurementSource = Literal["MANUAL", "AUTO"]
MetricCategory = Literal[
    "VITALS",
    "BIOMETRICS",
    "HABITS",
    "LABS",
    "VISION",
    "RESPIRATORY",
    "ENVIRONMENT",
]


def normalize_utc_timestamp(raw_value: str | None) -> str:
    if raw_value is None or not raw_value.strip():
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    cleaned = raw_value.strip()
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"

    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


class MetricCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_key: str
    display_name_en: str
    category: MetricCategory
    unit: str
    nominal_min: float
    nominal_max: float
    warning_min: float | None = None
    warning_max: float | None = None
    critical_min: float | None = None
    critical_threshold: float | None = None
    recommended_frequency_hours: float
    clinical_reference: str
    plausible_min: float | None = None
    plausible_max: float | None = None


class MeasurementItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_key: str = Field(..., min_length=1, max_length=80)
    value_num: float
    payload_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metric_key")
    @classmethod
    def strip_key(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Metric key must not be blank.")
        return trimmed

    @field_validator("value_num")
    @classmethod
    def reject_non_finite(cls, value: float) -> float:
        if math.isnan(value) or math.isinf(value):
            raise ValueError("Numeric measurement value must be finite.")
        return value


class MeasurementBatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Both are optional: the session decides the crew member and the mission its stage.
    crew_id: str | None = Field(default=None, max_length=32)
    mission_stage: MissionStage | None = None
    source_type: MeasurementSource = "MANUAL"
    recorded_at_utc: str | None = None
    items: list[MeasurementItemIn] = Field(..., min_length=1, max_length=64)

    @field_validator("crew_id")
    @classmethod
    def strip_crew(cls, value: str | None) -> str | None:
        trimmed = (value or "").strip()
        return trimmed or None

    @field_validator("recorded_at_utc")
    @classmethod
    def validate_utc(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_utc_timestamp(value)


class StreakUpdateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crew_id: str
    streak_date_utc: str
    logs_completed: int
    habits_met: bool
    daily_compliant: bool


class MeasurementIngestOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inserted_ids: list[int]
    alerts_created: list[int]
    mission_stage: MissionStage
    streak: StreakUpdateSummary
    recorded_at_utc: str


class MeasurementRowOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    crew_id: str
    metric_key: str
    mission_stage: MissionStage
    source_type: MeasurementSource
    recorded_at_utc: str
    value_num: float | None = None
    payload_json: str
