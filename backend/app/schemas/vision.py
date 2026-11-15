from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VisionStageFilter = Literal["ALL", "LAUNCH", "MISSION", "RETURN"]
VisionHudTone = Literal["reference", "warn", "critical"]
VisionMetricTone = Literal["nominal", "warn", "critical"]
VisionReviewStatus = Literal["PENDING_REVIEW", "APPROVED", "REJECTED", "PROMOTED_TO_GUIDE"]


class VisionEyeArcOut(BaseModel):
    side: Literal["LEFT", "RIGHT"]
    label: str
    sheath_mm: float
    display_value: str
    baseline_mm: float
    delta_mm: float
    status_label: str
    tone: VisionHudTone


class VisionClinicalMetricOut(BaseModel):
    key: str
    label: str
    subtitle: str
    display_value: str
    unit: str
    badge_label: str
    tone: VisionMetricTone
    marker_pct: float = Field(..., ge=0.0, le=100.0)
    nominal_band_start_pct: float = Field(..., ge=0.0, le=100.0)
    nominal_band_width_pct: float = Field(..., ge=0.0, le=100.0)


class VisionTrendPointOut(BaseModel):
    label: str
    left_mm: float
    right_mm: float
    is_projected: bool = False


class VisionPreventiveStepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_number: int = Field(..., ge=1, le=3)
    code_label: str = Field(..., min_length=3, max_length=64)
    title: str = Field(..., min_length=3, max_length=80)
    description: str = Field(..., min_length=6, max_length=240)
    accent_tone: Literal["ok", "ice"] = "ok"


class VisionPreventiveStepOut(BaseModel):
    step_number: int
    code_label: str
    title: str
    description: str
    accent_tone: Literal["ok", "ice"]


class VisionReviewCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_status: Literal["APPROVED", "REJECTED", "PROMOTED_TO_GUIDE"] = "APPROVED"
    physician_notes_en: str | None = Field(default=None, max_length=500)
    preventive_steps: list[VisionPreventiveStepIn] | None = Field(
        default=None,
        min_length=1,
        max_length=3,
    )


class VisionReviewCreatedOut(BaseModel):
    diagnosis_id: int
    crew_id: str
    validation_status: VisionReviewStatus
    validated_by: str
    reviewer_label: str
    validated_at_utc: str
    physician_notes_en: str | None = None


class VisionExamOut(BaseModel):
    crew_id: str
    crew_code: str
    selected_stage: VisionStageFilter
    stage_has_records: bool
    mission_day: int
    header_status_badge: str
    overall_tone: VisionHudTone
    alert_headline: str
    review_status: VisionReviewStatus
    reviewed_by_label: str
    physician_notes_en: str | None = None
    left_eye: VisionEyeArcOut
    right_eye: VisionEyeArcOut
    ocular_metrics: list[VisionClinicalMetricOut]
    latest_scan_heading: str
    latest_scan_subtitle: str
    baseline_band_label: str
    baseline_band_min_mm: float
    baseline_band_max_mm: float
    alert_threshold_label: str
    alert_threshold_mm: float
    right_legend_label: str
    left_legend_label: str
    trend_points: list[VisionTrendPointOut]
    steps_badge: str
    preventive_steps: list[VisionPreventiveStepOut]
