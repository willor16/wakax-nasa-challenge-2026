from typing import Literal

from pydantic import BaseModel, Field

OrganType = Literal["CARDIAC", "PULMONARY"]
CardiacSite = Literal["aortic", "pulmonic", "tricuspid", "mitral"]
PulmonarySite = Literal["upper_left", "upper_right", "lower_left", "lower_right"]
AnatomicalSite = Literal[
    "aortic",
    "pulmonic",
    "tricuspid",
    "mitral",
    "upper_left",
    "upper_right",
    "lower_left",
    "lower_right",
]
MissionStageLiteral = Literal["LAUNCH", "MISSION", "RETURN"]
AuscultationStageFilter = Literal["ALL", "LAUNCH", "MISSION", "RETURN"]
AuscultationTone = Literal["reference", "warn", "critical"]
AuscultationMetricTone = Literal["nominal", "warn", "critical"]


class AuscultationSiteStatusOut(BaseModel):
    site_key: AnatomicalSite
    organ_type: OrganType
    short_label: str
    placement_title: str
    saved: bool
    duration_sec: int | None = None
    sample_id: int | None = None
    recorded_at_utc: str | None = None
    status_text: str


class AuscultationOrganSummaryOut(BaseModel):
    organ_type: OrganType
    title: str
    primary_metric: str
    secondary_badge: str
    sites_summary: str
    detail_line: str
    tone: AuscultationTone
    saved_sites_count: int = Field(..., ge=0, le=4)
    total_sites_count: int = Field(default=4, ge=1, le=4)
    latest_sample_id: int | None = None


class AuscultationMetricBarOut(BaseModel):
    key: str
    label: str
    target_label: str
    display_value: str
    fill_pct: float = Field(..., ge=0.0, le=100.0)
    tone: AuscultationMetricTone


class AuscultationCo2PointOut(BaseModel):
    label: str
    co2_mmhg: float
    co2_ppm: float


class AuscultationResultsOut(BaseModel):
    crew_id: str
    crew_code: str
    full_name: str
    role: str
    selected_stage: AuscultationStageFilter
    active_mission_stage: str
    stage_has_records: bool
    overall_tone: AuscultationTone
    results_badge: str
    signal_quality_pct: int = Field(..., ge=0, le=100)
    signal_badge: str
    cabin_noise_dba: float
    noise_gate_limit_dba: float = 55.0
    is_noise_safe: bool
    heart_rate_bpm: float
    respiratory_rate_rpm: float
    spo2_pct: float
    cardiac_summary: AuscultationOrganSummaryOut
    pulmonary_summary: AuscultationOrganSummaryOut
    clinical_bars: list[AuscultationMetricBarOut]
    cardiac_channel_subtitle: str
    pulmonary_channel_subtitle: str
    phonocardiogram_samples: list[float]
    pulmonary_envelope_samples: list[float]
    co2_badge: str
    co2_tone: AuscultationTone
    co2_current_mmhg: float
    co2_target_max_mmhg: float = 3.2
    co2_alert_limit_mmhg: float = 4.0
    co2_trend: list[AuscultationCo2PointOut]
    cardiac_sites: list[AuscultationSiteStatusOut]
    pulmonary_sites: list[AuscultationSiteStatusOut]
    cardiac_progress_summary: str
    pulmonary_progress_summary: str


class AuscultationSampleCreatedOut(BaseModel):
    sample_id: int
    crew_id: str
    mission_stage: MissionStageLiteral
    organ_type: OrganType
    anatomical_site: AnatomicalSite
    duration_sec: int
    cabin_noise_dba: float
    file_rel_path: str
    sha256_hex: str
    recorded_at_utc: str
    signal_quality_pct: int
    streak: dict
