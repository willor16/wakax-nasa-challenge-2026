from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SleepPeriod = Literal["last_night", "7d", "14d", "30d"]
SleepStageType = Literal["DEEP", "REM", "LIGHT", "AWAKE"]
MissionStage = Literal["LAUNCH", "MISSION", "RETURN"]
HudTagTone = Literal["reference", "warn", "critical"]


class SleepStageBoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: SleepStageType
    start_utc: str = Field(..., min_length=10, max_length=40)
    end_utc: str = Field(..., min_length=10, max_length=40)
    duration_min: int | None = Field(default=None, ge=1, le=720)


class SleepSessionCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crew_id: str = Field(..., min_length=2, max_length=32)
    mission_stage: MissionStage = "MISSION"
    sleep_start_utc: str = Field(..., min_length=10, max_length=40)
    sleep_end_utc: str = Field(..., min_length=10, max_length=40)
    deep_min: int | None = Field(default=None, ge=0, le=600)
    rem_min: int | None = Field(default=None, ge=0, le=600)
    light_min: int | None = Field(default=None, ge=0, le=720)
    awake_min: int | None = Field(default=None, ge=0, le=480)
    sleep_score: int | None = Field(default=None, ge=0, le=100)
    stages: list[SleepStageBoutIn] | None = None

    @model_validator(mode="after")
    def validate_stage_totals(self) -> "SleepSessionCreateIn":
        explicit = [self.deep_min, self.rem_min, self.light_min, self.awake_min]
        if any(v is not None for v in explicit) and not all(v is not None for v in explicit):
            raise ValueError(
                "Provide all four stage durations "
                "(deep_min, rem_min, light_min, awake_min) or omit all four."
            )
        return self


class SleepSessionCreatedOut(BaseModel):
    session_id: int
    crew_id: str
    mission_stage: MissionStage
    sleep_start_utc: str
    sleep_end_utc: str
    total_sleep_min: int
    time_in_bed_min: int
    sleep_score: int
    sleep_efficiency_pct: float
    bouts_inserted: int


class SleepStageCardOut(BaseModel):
    stage: SleepStageType
    label: str
    duration_min: int
    duration_display: str
    badge_label: str
    badge_tone: HudTagTone
    share_pct: int
    subtitle: str
    bar_fill_pct: float = Field(..., ge=0.0, le=100.0)


class SleepAxisTickOut(BaseModel):
    offset_min: float
    label: str


class SleepRibbonLegendItemOut(BaseModel):
    stage: SleepStageType
    label: str


class SleepRibbonBoutOut(BaseModel):
    stage: SleepStageType
    lane_index: int = Field(..., ge=1, le=4)
    prev_lane_index: int | None = Field(default=None, ge=1, le=4)
    start_offset_min: float = Field(..., ge=0.0)
    end_offset_min: float = Field(..., ge=0.0)
    duration_min: int = Field(..., ge=1)
    start_hm: str
    end_hm: str


class SleepStageLapseRowOut(BaseModel):
    stage: SleepStageType
    label: str
    intervals_summary: str
    bouts_count: int
    bouts_label: str
    avg_max_label: str
    total_display: str


class SleepMonitorOut(BaseModel):
    crew_id: str
    crew_code: str
    period: SleepPeriod
    nights_analyzed: int
    mission_day: int
    last_night_tab_label: str
    rest_window_badge: str
    header_score_badge: str
    quality_tag: str
    quality_tone: HudTagTone
    sleep_score: int
    score_subtitle: str
    sleep_time_heading: str
    total_sleep_min: int
    total_sleep_display: str
    target_label: str
    target_met: bool
    in_bed_min: int
    in_bed_display: str
    efficiency_pct: int
    efficiency_label: str
    stage_cards: list[SleepStageCardOut]
    ribbon_title: str
    cycle_count: int
    cycle_badge: str
    rest_window_inline: str
    window_total_min: float
    axis_ticks: list[SleepAxisTickOut]
    ribbon_legend: list[SleepRibbonLegendItemOut]
    ribbon_bouts: list[SleepRibbonBoutOut]
    total_bouts: int
    bouts_badge: str
    lapse_rows: list[SleepStageLapseRowOut]
