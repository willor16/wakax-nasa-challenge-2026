from typing import Literal

from pydantic import BaseModel, Field

MissionStage = Literal["LAUNCH", "MISSION", "RETURN"]
StatusTone = Literal["nominal", "warn", "critical"]
HudTagTone = Literal["reference", "warn", "critical"]
CrewRole = Literal["ASTRONAUT", "PILOT", "OPERATOR", "PHYSICIAN"]


class CrewDemographicsOut(BaseModel):
    id: str
    code: str
    full_name: str
    short_name: str
    role: CrewRole
    role_badge: str
    age: int | None
    sex: str | None
    sex_display: str
    blood_type: str | None
    baseline_height_cm: float


class ProfileMissionContextOut(BaseModel):
    mission_code: str
    mission_name: str
    current_stage: MissionStage
    selected_stage: MissionStage
    stage_has_records: bool
    mission_day: int = Field(..., ge=1)
    mission_day_code: str
    elapsed_days_label: str
    utc_hm: str
    server_utc: str


class StageMetricSnapshotOut(BaseModel):
    stage: MissionStage
    has_records: bool
    body_weight_kg: float | None
    resting_hr_bpm: float | None
    vo2_max_ml_kg_min: float | None
    optic_sheath_right_mm: float | None


class BiometricCardOut(BaseModel):
    key: str
    label: str
    value: float
    display_value: str
    unit: str
    baseline_mean: float | None
    baseline_std: float | None
    z_score: float | None
    subtitle: str
    status_tone: StatusTone


class BiometricScanOut(BaseModel):
    scan_label: str
    scan_tone: HudTagTone
    core_temp_c: float
    core_temp_display: str
    hydration_liters: float
    hydration_target_liters: float
    hydration_display: str
    cardiac_tone: StatusTone
    pulmonary_tone: StatusTone
    ocular_tone: StatusTone


class EnvironmentGaugeOut(BaseModel):
    key: str
    label: str
    value: float
    display_value: str
    subtitle: str
    arc_pct: float = Field(..., ge=0.0, le=100.0)
    status_tone: StatusTone


class WorkTimeRowOut(BaseModel):
    key: str
    label: str
    subtitle: str
    display_value: str
    status_tone: StatusTone


class EnvironmentAndWorkOut(BaseModel):
    habitat_tag: str
    co2_ppm: float
    co2_mmhg: float
    radiation_msv: float
    solar_event_flag: bool
    gauges: list[EnvironmentGaugeOut]
    work_header: str
    work_rows: list[WorkTimeRowOut]


class ClinicalProgressItemOut(BaseModel):
    key: str
    label: str
    subtitle: str
    display_value: str
    unit: str
    status_label: str
    status_tone: StatusTone
    progress_pct: float = Field(..., ge=0.0, le=100.0)
    band_start_pct: float = Field(..., ge=0.0, le=100.0)
    band_width_pct: float = Field(..., ge=0.0, le=100.0)
    on_target: bool


class DailyVitalsHabitsOut(BaseModel):
    tag_text: str
    header_target_badge: str
    on_target_count: int
    total_count: int
    items: list[ClinicalProgressItemOut]


class LiveEcgOut(BaseModel):
    rhythm_label: str
    rhythm_tone: HudTagTone
    lead_label: str
    resting_hr_bpm: float
    hrv_rmssd_ms: float
    body_temp_c: float
    header_summary: str
    sample_rate_hz: int
    samples_mv: list[float]


class ClinicalLabCardOut(BaseModel):
    key: str
    label: str
    status_label: str
    status_tone: StatusTone
    display_value: str
    detail: str


class CrewProfileOut(BaseModel):
    crew: CrewDemographicsOut
    mission: ProfileMissionContextOut
    stage_comparison: list[StageMetricSnapshotOut]
    biometrics: list[BiometricCardOut]
    biometric_scan: BiometricScanOut
    environment_work: EnvironmentAndWorkOut
    daily_vitals: DailyVitalsHabitsOut
    live_ecg: LiveEcgOut
    clinical_labs: list[ClinicalLabCardOut]
