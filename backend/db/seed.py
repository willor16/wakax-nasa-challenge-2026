"""Pre-flight database seeder for SpaceScan.

Builds a realistic 47-day mission for the four crew members from the research
reference ranges (``db/seed_snapshots/reference_ranges.json``): seven pre-flight
days that form each personal baseline, then daily mission records whose trends
follow the published spaceflight effects (slow bone and muscle loss, optic nerve
sheath swelling, sleep and stress changes). The timeline is anchored to today, so
the demo always opens on mission Day 047.

All values are simulated training data; every alert, streak and readiness score
is produced afterwards by the same engines the app uses for live data.

Run with ``uv run python -m db.seed`` (add ``--reset`` to start from scratch).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from app.auth_utils import hash_pin
from app.config import AUDIO_STORAGE_DIR, DB_PATH, SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import init_db, open_connection
from app.services import acoustics
from app.services.contracts import evaluate_alerts
from app.services.crew_metrics import compute_crew_baselines
from app.services.habits import recompute_day
from app.services.mission_clock import TS_FORMAT
from app.services.reference_ranges import personal_targets
from app.services.scheduled_checks import refresh_scheduled_checks
from app.services.sensor_simulator import ecg_payload
from app.services.sleep_metrics import build_night, sleep_score
from app.services.wiki_seed import load_medical_guide

MISSION_DAY_TODAY = 47
PRE_FLIGHT_DAYS = 7
AUDIO_SAMPLE_RATE = 4000


def _ts(moment: datetime) -> str:
    return moment.strftime(TS_FORMAT)


@dataclass
class Story:
    """Pre-flight mean, Day-47 value and day-to-day spread for one metric."""

    start: float
    end: float
    sd: float
    digits: int = 1


@dataclass
class CrewPlan:
    crew_id: str
    vitals: dict[str, Story]
    habits: dict[str, Story]
    body: dict[str, Story]
    labs: dict[str, Story]
    ocular: dict[str, list[float]]
    sleep_hours: Story
    sleep_today_min: int
    hydration_today_pct: float
    missed_days: set[int]
    work: tuple[str, str, int]
    eva_today_min: int = 0
    eva_days: set[int] = field(default_factory=set)
    mood: tuple[float, float, float, float] = (4.4, 1.8, 1.5, 4.6)
    mood_state: str = "CALM"
    reaction_ms: float = 270.0
    accuracy_pct: float = 98.0
    lapses: int = 0


# Ocular exams: three pre-flight scans, then Day 1, 15, 30 and 47.
OCULAR_DAYS = (-6, -4, -2, 1, 15, 30, 47)

PLANS: tuple[CrewPlan, ...] = (
    CrewPlan(
        crew_id="ID-01",
        vitals={
            "resting_hr_bpm": Story(62, 64, 2.0, 0),
            "hrv_rmssd_ms": Story(70, 72, 4.0, 0),
            "spo2_pct": Story(98.4, 98, 0.5, 0),
            "bp_systolic_mmhg": Story(114, 118, 3.0, 0),
            "bp_diastolic_mmhg": Story(74, 76, 2.5, 0),
            "body_temp_c": Story(36.7, 36.8, 0.12),
            "respiratory_rate_brpm": Story(14.0, 14.2, 0.5),
        },
        habits={"calories_kcal": Story(2050, 2020, 90, 0), "exercise_min": Story(45, 40, 6, 0)},
        body={
            "height_cm": Story(171.0, 173.2, 0.15),
            "body_weight_kg": Story(64.5, 63.8, 0.25),
            "muscle_mass_kg": Story(22.7, 22.4, 0.08),
            "bone_density_g_cm2": Story(1.19, 1.18, 0.003, 3),
            "vo2_max_ml_kg_min": Story(46.0, 44.8, 0.4),
            "orthostatic_hr_delta_bpm": Story(8, 9, 1.0, 0),
            "cardiorespiratory_index": Story(86, 84, 1.5, 0),
        },
        labs={
            "blood_glucose_mg_dl": Story(88, 89, 3.0, 0),
            "hemoglobin_g_dl": Story(13.9, 13.8, 0.2),
            "urine_specific_gravity": Story(1.012, 1.018, 0.002, 3),
            "urine_color_scale": Story(2, 3, 0.4, 0),
        },
        ocular={
            "optic_sheath_right_mm": [4.65, 4.70, 4.75, 4.9, 5.3, 5.6, 5.9],
            "optic_sheath_left_mm": [4.55, 4.60, 4.65, 4.8, 5.1, 5.3, 5.5],
            "iop_right_mmhg": [14.6, 15.0, 15.4, 15.6, 15.9, 16.0, 16.2],
            "iop_left_mmhg": [14.4, 14.8, 15.0, 15.2, 15.5, 15.6, 15.8],
            "retinal_thickness_um": [101, 102, 103, 102, 103, 104, 104],
            "visual_acuity_snellen": [20, 20, 20, 20, 20, 20, 20],
        },
        sleep_hours=Story(7.5, 7.2, 0.25, 2),
        sleep_today_min=432,
        hydration_today_pct=0.86,
        missed_days={9, 28, 33},
        work=("IVA", "Command Bridge", 320),
        mood=(4.5, 1.8, 1.4, 4.7),
        mood_state="CALM",
        reaction_ms=268,
        accuracy_pct=98.4,
    ),
    CrewPlan(
        crew_id="ID-02",
        vitals={
            "resting_hr_bpm": Story(64, 76, 2.5, 0),
            "hrv_rmssd_ms": Story(70, 48, 4.5, 0),
            "spo2_pct": Story(98.6, 98, 0.5, 0),
            "bp_systolic_mmhg": Story(118, 124, 3.0, 0),
            "bp_diastolic_mmhg": Story(77, 80, 2.5, 0),
            "body_temp_c": Story(36.6, 36.7, 0.12),
            "respiratory_rate_brpm": Story(13.5, 15.0, 0.6),
        },
        habits={"calories_kcal": Story(2600, 2480, 60, 0), "exercise_min": Story(50, 38, 3, 0)},
        body={
            "height_cm": Story(182.0, 184.1, 0.15),
            "body_weight_kg": Story(79.0, 77.6, 0.3),
            "muscle_mass_kg": Story(33.5, 32.9, 0.1),
            "bone_density_g_cm2": Story(1.27, 1.25, 0.003, 3),
            "vo2_max_ml_kg_min": Story(50.0, 48.6, 0.5),
            "orthostatic_hr_delta_bpm": Story(10, 14, 1.2, 0),
            "cardiorespiratory_index": Story(85, 76, 2.0, 0),
        },
        labs={
            "blood_glucose_mg_dl": Story(91, 94, 3.0, 0),
            "hemoglobin_g_dl": Story(15.1, 14.8, 0.2),
            "urine_specific_gravity": Story(1.014, 1.024, 0.002, 3),
            "urine_color_scale": Story(3, 5, 0.5, 0),
        },
        ocular={
            "optic_sheath_right_mm": [4.25, 4.30, 4.30, 4.4, 4.5, 4.55, 4.6],
            "optic_sheath_left_mm": [4.20, 4.25, 4.30, 4.3, 4.4, 4.50, 4.6],
            "iop_right_mmhg": [15.0, 15.2, 15.4, 15.5, 15.8, 16.0, 16.1],
            "iop_left_mmhg": [15.0, 15.1, 15.3, 15.4, 15.6, 15.8, 15.9],
            "retinal_thickness_um": [98, 99, 98, 99, 99, 100, 100],
            "visual_acuity_snellen": [20, 20, 20, 20, 20, 20, 20],
        },
        sleep_hours=Story(7.4, 5.67, 0.3, 2),
        sleep_today_min=340,
        hydration_today_pct=0.64,
        missed_days={6, 17, 24, 35, 47},
        work=("IVA", "Life Support Bay", 370),
        mood=(3.4, 3.2, 2.6, 3.8),
        mood_state="TIRED",
        reaction_ms=318,
        accuracy_pct=94.2,
        lapses=2,
    ),
    CrewPlan(
        crew_id="ID-03",
        vitals={
            "resting_hr_bpm": Story(62, 61, 2.0, 0),
            "hrv_rmssd_ms": Story(76, 78, 4.0, 0),
            "spo2_pct": Story(98.8, 99, 0.4, 0),
            "bp_systolic_mmhg": Story(112, 113, 3.0, 0),
            "bp_diastolic_mmhg": Story(72, 72, 2.0, 0),
            "body_temp_c": Story(36.7, 36.7, 0.1),
            "respiratory_rate_brpm": Story(13.2, 13.4, 0.5),
        },
        habits={"calories_kcal": Story(2000, 2010, 80, 0), "exercise_min": Story(42, 44, 5, 0)},
        body={
            "height_cm": Story(168.0, 170.0, 0.15),
            "body_weight_kg": Story(60.0, 59.8, 0.25),
            "muscle_mass_kg": Story(21.0, 20.8, 0.07),
            "bone_density_g_cm2": Story(1.15, 1.145, 0.003, 3),
            "vo2_max_ml_kg_min": Story(42.0, 41.4, 0.4),
            "orthostatic_hr_delta_bpm": Story(7, 8, 1.0, 0),
            "cardiorespiratory_index": Story(88, 88, 1.2, 0),
        },
        labs={
            "blood_glucose_mg_dl": Story(86, 87, 3.0, 0),
            "hemoglobin_g_dl": Story(13.4, 13.3, 0.2),
            "urine_specific_gravity": Story(1.012, 1.013, 0.002, 3),
            "urine_color_scale": Story(2, 2, 0.4, 0),
        },
        ocular={
            "optic_sheath_right_mm": [4.15, 4.20, 4.20, 4.25, 4.3, 4.35, 4.4],
            "optic_sheath_left_mm": [4.10, 4.15, 4.20, 4.20, 4.25, 4.3, 4.35],
            "iop_right_mmhg": [13.6, 13.8, 14.0, 14.0, 14.2, 14.3, 14.4],
            "iop_left_mmhg": [13.5, 13.6, 13.9, 14.0, 14.1, 14.2, 14.3],
            "retinal_thickness_um": [97, 98, 98, 98, 99, 99, 99],
            "visual_acuity_snellen": [20, 20, 20, 20, 20, 20, 20],
        },
        sleep_hours=Story(7.6, 7.75, 0.2, 2),
        sleep_today_min=465,
        hydration_today_pct=1.0,
        missed_days={12, 28},
        work=("IVA", "Medical Bay", 290),
        mood=(4.6, 1.5, 1.3, 4.8),
        mood_state="FOCUSED",
        reaction_ms=255,
        accuracy_pct=99.1,
    ),
    CrewPlan(
        crew_id="ID-04",
        vitals={
            "resting_hr_bpm": Story(62, 82, 2.0, 0),
            "hrv_rmssd_ms": Story(68, 62, 4.0, 0),
            "spo2_pct": Story(98.6, 98, 0.5, 0),
            "bp_systolic_mmhg": Story(116, 122, 3.0, 0),
            "bp_diastolic_mmhg": Story(75, 78, 2.5, 0),
            "body_temp_c": Story(36.6, 36.9, 0.12),
            "respiratory_rate_brpm": Story(13.8, 16.0, 0.5),
        },
        habits={"calories_kcal": Story(2700, 2750, 100, 0), "exercise_min": Story(50, 48, 6, 0)},
        body={
            "height_cm": Story(176.0, 178.0, 0.15),
            "body_weight_kg": Story(72.0, 70.9, 0.3),
            "muscle_mass_kg": Story(31.0, 30.2, 0.1),
            "bone_density_g_cm2": Story(1.24, 1.22, 0.003, 3),
            "vo2_max_ml_kg_min": Story(49.0, 46.5, 0.5),
            "orthostatic_hr_delta_bpm": Story(9, 12, 1.0, 0),
            "cardiorespiratory_index": Story(87, 81, 1.5, 0),
        },
        labs={
            "blood_glucose_mg_dl": Story(90, 92, 3.0, 0),
            "hemoglobin_g_dl": Story(15.0, 14.7, 0.2),
            "urine_specific_gravity": Story(1.013, 1.016, 0.002, 3),
            "urine_color_scale": Story(2, 3, 0.4, 0),
        },
        ocular={
            "optic_sheath_right_mm": [4.35, 4.40, 4.40, 4.5, 4.6, 4.7, 4.8],
            "optic_sheath_left_mm": [4.30, 4.35, 4.40, 4.45, 4.55, 4.65, 4.7],
            "iop_right_mmhg": [14.4, 14.6, 14.8, 15.0, 15.4, 15.8, 16.0],
            "iop_left_mmhg": [14.3, 14.5, 14.7, 14.9, 15.2, 15.6, 15.9],
            "retinal_thickness_um": [100, 101, 101, 101, 102, 102, 103],
            "visual_acuity_snellen": [20, 20, 20, 20, 20, 20, 20],
        },
        sleep_hours=Story(7.5, 6.58, 0.25, 2),
        sleep_today_min=395,
        hydration_today_pct=0.88,
        missed_days={14, 30, 38},
        work=("EVA", "Post-EVA Rest", 222),
        eva_today_min=222,
        eva_days={12, 26, 40, 47},
        mood=(4.2, 2.2, 1.8, 4.5),
        mood_state="FOCUSED",
        reaction_ms=276,
        accuracy_pct=97.6,
    ),
)


def _value(story: Story, progress: float, rng: random.Random, exact: bool = False) -> float:
    base = story.start + (story.end - story.start) * progress
    value = base if exact else rng.gauss(base, story.sd)
    return round(value, story.digits) if story.digits else float(round(value))


class Writer:
    """Inserts rows and keeps the ids that need an alert evaluation afterwards."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.pending: list[int] = []

    def measure(
        self,
        crew_id: str,
        metric_key: str,
        stage: str,
        at: datetime,
        value: float,
        payload: dict | None = None,
        source: str = "MANUAL",
    ) -> int:
        cursor = self.conn.execute(
            """INSERT INTO measurements (crew_id, metric_key, mission_stage, source_type,
               recorded_at_utc, value_num, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (crew_id, metric_key, stage, source, _ts(at), value, json.dumps(payload or {})),
        )
        if stage != "LAUNCH":
            self.pending.append(int(cursor.lastrowid))
        return int(cursor.lastrowid)


def _clamp_to_now(moment: datetime, now: datetime) -> datetime:
    return min(moment, now - timedelta(minutes=5))


def _seed_reference_rows(
    conn: sqlite3.Connection, snapshot: dict, launch: datetime, now: datetime
) -> None:
    m = snapshot["mission"]
    conn.execute(
        """INSERT OR REPLACE INTO mission (id, mission_code, mission_name, current_stage,
           launch_utc, planned_return_utc, earth_latency_min, quiet_hours_start_utc,
           quiet_hours_end_utc, updated_at_utc) VALUES (1, ?, ?, 'MISSION', ?, ?, ?, ?, ?, ?)""",
        (
            m["mission_code"],
            m["mission_name"],
            _ts(launch),
            _ts(launch + timedelta(days=180)),
            m["earth_latency_min"],
            m["quiet_hours_start_utc"],
            m["quiet_hours_end_utc"],
            _ts(now),
        ),
    )
    for member in snapshot["crew_members"]:
        conn.execute(
            """INSERT OR IGNORE INTO crew_members (id, code, full_name, role, pin_hash, age, sex,
               blood_type, height_cm, title_en, is_active, created_at_utc, updated_at_utc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                member["id"],
                member["code"],
                member["full_name"],
                member["role"],
                hash_pin(member["pin"]),
                member["age"],
                member["sex"],
                member["blood_type"],
                member["height_cm"],
                member["title_en"],
                _ts(now),
                _ts(now),
            ),
        )
    load_medical_guide(conn)


def _day_start(launch: datetime, day: int) -> datetime:
    """UTC midnight of a mission day (Day 1 = launch day; pre-flight days are <= 0)."""
    return datetime.combine(launch.date(), time(0, 0), tzinfo=UTC) + timedelta(days=day - 1)


def _stage(day: int) -> str:
    return "LAUNCH" if day <= 0 else "MISSION"


def _seed_crew(
    conn: sqlite3.Connection,
    w: Writer,
    plan: CrewPlan,
    launch: datetime,
    now: datetime,
    rng: random.Random,
) -> None:
    crew_id = plan.crew_id
    first_day = 1 - PRE_FLIGHT_DAYS
    for day in range(first_day, MISSION_DAY_TODAY + 1):
        stage = _stage(day)
        start = _day_start(launch, day)
        progress = 0.0 if day <= 0 else day / MISSION_DAY_TODAY
        today = day == MISSION_DAY_TODAY
        missed = day in plan.missed_days

        morning = (
            _clamp_to_now(start + timedelta(hours=7, minutes=30), now)
            if today
            else start + timedelta(hours=7, minutes=30)
        )
        for key, story in plan.vitals.items():
            w.measure(crew_id, key, stage, morning, _value(story, progress, rng, exact=today))
        if day % 3 == 0 or day <= 0:
            w.measure(
                crew_id,
                "body_weight_kg",
                stage,
                morning + timedelta(minutes=10),
                _value(plan.body["body_weight_kg"], progress, rng, exact=today),
            )

        # Daily habits, logged in the evening (today: what was logged so far).
        evening = start + timedelta(hours=20)
        if today:
            evening = _clamp_to_now(start + timedelta(hours=14), now)
        crew = conn.execute(
            "SELECT sex, age, height_cm FROM crew_members WHERE id = ?", (crew_id,)
        ).fetchone()
        target = personal_targets(dict(crew), plan.body["body_weight_kg"].start).hydration_ml
        if today:
            hydration = round(target * plan.hydration_today_pct / 50) * 50
        elif missed:
            hydration = round(target * 0.62 / 50) * 50
        else:
            hydration = round(rng.uniform(1.0, 1.12) * target / 50) * 50
        w.measure(crew_id, "hydration_ml", stage, evening, hydration)
        calories = _value(plan.habits["calories_kcal"], progress, rng, exact=today)
        w.measure(crew_id, "calories_kcal", stage, evening, calories * (0.8 if missed else 1.0))
        is_eva = day in plan.eva_days
        exercise = 0 if is_eva else _value(plan.habits["exercise_min"], progress, rng, exact=today)
        if missed and not is_eva:
            exercise = 15
        w.measure(crew_id, "exercise_min", stage, evening, exercise)
        mode, location, shift = plan.work
        if is_eva:
            eva_min = plan.eva_today_min if today else rng.choice((210, 228, 245))
            w.measure(
                crew_id,
                "eva_shift_min",
                stage,
                evening,
                eva_min,
                {"mode": "EVA", "location_en": "Exterior Truss"},
            )
            w.measure(
                crew_id,
                "work_shift_min",
                stage,
                evening,
                eva_min,
                {"mode": "EVA", "location_en": location if today else "Exterior Truss"},
            )
        else:
            w.measure(
                crew_id,
                "work_shift_min",
                stage,
                evening,
                shift if today else shift + rng.randint(-25, 25),
                {"mode": "IVA", "location_en": location},
            )

        # Weekly body composition, labs and fitness; ECG strip each morning.
        if day <= 0 or day % 7 == 0 or today:
            for key in (
                "height_cm",
                "muscle_mass_kg",
                "orthostatic_hr_delta_bpm",
                "cardiorespiratory_index",
            ):
                w.measure(
                    crew_id,
                    key,
                    stage,
                    morning + timedelta(minutes=20),
                    _value(plan.body[key], progress, rng, exact=today),
                )
            for key in ("urine_specific_gravity", "urine_color_scale"):
                w.measure(
                    crew_id,
                    key,
                    stage,
                    morning + timedelta(minutes=5),
                    _value(plan.labs[key], progress, rng, exact=today),
                )
        if day <= 0 or day % 14 == 0 or today:
            w.measure(
                crew_id,
                "blood_glucose_mg_dl",
                stage,
                morning + timedelta(minutes=2),
                _value(plan.labs["blood_glucose_mg_dl"], progress, rng, exact=today),
            )
            w.measure(
                crew_id,
                "vo2_max_ml_kg_min",
                stage,
                morning + timedelta(hours=2),
                _value(plan.body["vo2_max_ml_kg_min"], progress, rng, exact=today),
            )
        if day in (-5, -3, -1) or day in (15, 30, 45) or today:
            w.measure(
                crew_id,
                "hemoglobin_g_dl",
                stage,
                morning + timedelta(minutes=3),
                _value(plan.labs["hemoglobin_g_dl"], progress, rng, exact=today),
            )
            w.measure(
                crew_id,
                "bone_density_g_cm2",
                stage,
                morning + timedelta(hours=1),
                _value(plan.body["bone_density_g_cm2"], progress, rng, exact=today),
            )
        if day >= MISSION_DAY_TODAY - 13 or day <= 0:
            hr_story = plan.vitals["resting_hr_bpm"]
            w.measure(
                crew_id,
                "ecg_lead_ii_mv",
                stage,
                morning + timedelta(minutes=1),
                1.2,
                ecg_payload(_value(hr_story, progress, rng, exact=today), seed=day)
                | {"heart_rate_bpm": _value(hr_story, progress, rng, exact=today)},
                source="AUTO",
            )

        if day in OCULAR_DAYS:
            index = OCULAR_DAYS.index(day)
            exam_at = (
                _clamp_to_now(start + timedelta(hours=11, minutes=20), now)
                if today
                else start + timedelta(hours=11, minutes=20)
            )
            for key, values in plan.ocular.items():
                w.measure(crew_id, key, stage, exam_at, values[index])

        _seed_night(conn, plan, day, launch, rng, now)
        _seed_mind(conn, plan, day, launch, rng, now)


def _seed_night(
    conn: sqlite3.Connection,
    plan: CrewPlan,
    day: int,
    launch: datetime,
    rng: random.Random,
    now: datetime,
) -> None:
    """Night that ends on the morning of ``day``."""
    today = day == MISSION_DAY_TODAY
    missed = day in plan.missed_days
    progress = 0.0 if day <= 0 else day / MISSION_DAY_TODAY
    if today:
        total = plan.sleep_today_min
    elif missed:
        total = int(rng.uniform(5.3, 5.9) * 60)
    else:
        total = int(_value(plan.sleep_hours, progress, rng) * 60)
    awake = int(rng.uniform(18, 30)) if not today else 24
    deep_pct = rng.uniform(17, 23) if not today else 22
    rem_pct = rng.uniform(20, 25) if not today else 25
    onset = _day_start(launch, day) - timedelta(hours=1, minutes=rng.randint(30, 50))
    if today and plan.crew_id == "ID-01":
        onset = _day_start(launch, day) - timedelta(hours=1, minutes=42)
    bouts = build_night(total, awake, deep_pct, rem_pct, [rng.uniform(-0.3, 0.3) for _ in range(7)])
    in_bed = sum(m for _, m in bouts)
    end = onset + timedelta(minutes=in_bed)
    if end >= now:
        return
    minutes = {s: sum(m for st, m in bouts if st == s) for s in ("DEEP", "REM", "LIGHT", "AWAKE")}
    asleep = in_bed - minutes["AWAKE"]
    score = sleep_score(asleep, in_bed, minutes["DEEP"], minutes["REM"], minutes["AWAKE"])
    cursor = conn.execute(
        """INSERT INTO sleep_sessions (crew_id, mission_stage, sleep_start_utc, sleep_end_utc,
           total_sleep_min, time_in_bed_min, sleep_score, sleep_efficiency_pct, deep_min, rem_min,
           light_min, awake_min, recorded_at_utc, stages_recorded)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (
            plan.crew_id,
            _stage(day),
            _ts(onset),
            _ts(end),
            asleep,
            in_bed,
            score,
            round(asleep / in_bed * 100, 1),
            minutes["DEEP"],
            minutes["REM"],
            minutes["LIGHT"],
            minutes["AWAKE"],
            _ts(end),
        ),
    )
    session_id = int(cursor.lastrowid)
    cursor_at = onset
    for stage, mins in bouts:
        conn.execute(
            """INSERT INTO sleep_stages (session_id, stage, start_utc, end_utc, duration_min)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, stage, _ts(cursor_at), _ts(cursor_at + timedelta(minutes=mins)), mins),
        )
        cursor_at += timedelta(minutes=mins)


def _seed_mind(
    conn: sqlite3.Connection,
    plan: CrewPlan,
    day: int,
    launch: datetime,
    rng: random.Random,
    now: datetime,
) -> None:
    today = day == MISSION_DAY_TODAY
    at = _day_start(launch, day) + timedelta(hours=7, minutes=45)
    if at >= now:
        at = now - timedelta(minutes=10)
    mood, stress, lonely, motivation = plan.mood
    missed = day in plan.missed_days

    def scale(mean: float, worse: float = 0.0) -> int:
        value = mean if today else rng.gauss(mean + worse, 0.45)
        return int(min(5, max(1, round(value))))

    mood_s = scale(mood, -0.8 if missed else 0)
    stress_s = scale(stress, 0.8 if missed else 0)
    lonely_s = scale(lonely, 0.4 if missed else 0)
    motivation_s = scale(motivation, -0.5 if missed else 0)
    wellbeing = round(
        ((mood_s - 1) + (5 - stress_s) + (5 - lonely_s) + (motivation_s - 1)) / 16 * 100, 1
    )
    state = (
        plan.mood_state
        if today
        else ("TIRED" if missed else rng.choice(("CALM", "FOCUSED", plan.mood_state)))
    )
    session = conn.execute(
        "SELECT sleep_start_utc, sleep_end_utc FROM sleep_sessions WHERE crew_id = ? "
        "ORDER BY sleep_end_utc DESC LIMIT 1",
        (plan.crew_id,),
    ).fetchone()
    onset = session["sleep_start_utc"][11:16] if session else None
    wake = session["sleep_end_utc"][11:16] if session else None
    conn.execute(
        """INSERT INTO psych_tests (crew_id, mission_stage, mood_score, stress_score,
           loneliness_score, motivation_score, wellbeing_index, notes_en, recorded_at_utc,
           mood_state, sleep_onset_utc, wake_utc) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)""",
        (
            plan.crew_id,
            _stage(day),
            mood_s,
            stress_s,
            lonely_s,
            motivation_s,
            wellbeing,
            _ts(at),
            state,
            onset,
            wake,
        ),
    )
    if day % 2 == 1 or today or day <= 0:
        reaction = (
            plan.reaction_ms if today else rng.gauss(plan.reaction_ms + (25 if missed else 0), 9)
        )
        accuracy = plan.accuracy_pct if today else min(100.0, rng.gauss(plan.accuracy_pct, 0.8))
        lapses = (
            plan.lapses
            if today
            else max(0, round(rng.gauss(plan.lapses + (1 if missed else 0), 0.6)))
        )
        trials = 24
        valid = max(0, min(trials, round(trials * accuracy / 100)))
        conn.execute(
            """INSERT INTO cognitive_tests (crew_id, mission_stage, test_type, reaction_ms,
               accuracy_pct, attention_score, duration_sec, recorded_at_utc, trials_total,
               valid_responses, false_starts, lapses) VALUES (?, ?, 'REACTION_ARENA', ?, ?, ?, 120,
               ?, ?, ?, ?, ?)""",
            (
                plan.crew_id,
                _stage(day),
                round(reaction),
                round(accuracy, 1),
                round(max(0.0, 100 - lapses * 4 - max(0.0, reaction - 250) / 10), 1),
                _ts(at + timedelta(minutes=5)),
                trials,
                valid,
                0,
                lapses,
            ),
        )


def _seed_environment(
    conn: sqlite3.Connection, launch: datetime, now: datetime, rng: random.Random
) -> None:
    """Cabin readings: every 6 h for the mission, hourly for the last 2 days."""
    moment = _day_start(launch, 1)
    while moment < now:
        recent = now - moment < timedelta(days=2)
        hour = moment.hour
        co2_mmhg = 2.8 + 0.25 * math.sin((hour - 2) / 24 * 6.283) + rng.gauss(0, 0.06)
        conn.execute(
            """INSERT INTO environment_readings (co2_ppm, noise_dba, temp_c, humidity_pct,
               radiation_msv, solar_event_flag, recorded_at_utc, kp_index, location_en)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'Habitat A')""",
            (
                round(co2_mmhg / 760 * 1e6),
                round(rng.gauss(48, 0.8), 1),
                round(rng.gauss(21.8, 0.2), 1),
                round(rng.gauss(44, 1.2), 1),
                round(rng.gauss(0.42, 0.02), 2),
                _ts(moment),
                float(rng.choice((2, 3, 3, 3, 4))),
            ),
        )
        moment += timedelta(hours=1 if recent else 6)


def _seed_auscultation(
    conn: sqlite3.Connection, plan: CrewPlan, launch: datetime, now: datetime, audio_dir: Path
) -> None:
    hr = plan.vitals["resting_hr_bpm"].end
    rr = plan.vitals["respiratory_rate_brpm"].end
    for day, hr_value in (
        (
            40,
            plan.vitals["resting_hr_bpm"].start
            + (hr - plan.vitals["resting_hr_bpm"].start) * 40 / 47,
        ),
        (MISSION_DAY_TODAY, hr),
    ):
        at = _clamp_to_now(_day_start(launch, day) + timedelta(hours=8, minutes=10), now)
        sites = (("CARDIAC", s) for s in ("aortic", "pulmonic", "tricuspid", "mitral"))
        lung_sites = (
            ("PULMONARY", s) for s in ("upper_left", "upper_right", "lower_left", "lower_right")
        )
        for index, (organ, site) in enumerate([*sites, *lung_sites]):
            seed = hash((plan.crew_id, day, site)) % 10_000
            signal = (
                acoustics.simulate_heart(hr_value, 30, AUDIO_SAMPLE_RATE, seed)
                if organ == "CARDIAC"
                else acoustics.simulate_lungs(rr, 30, AUDIO_SAMPLE_RATE, seed)
            )
            data = acoustics.write_wav(signal, AUDIO_SAMPLE_RATE)
            findings = acoustics.analyse(signal, AUDIO_SAMPLE_RATE, organ).to_dict()
            name = f"{plan.crew_id}_{organ.lower()}_{site}_d{day:03d}.wav"
            (audio_dir / name).write_bytes(data)
            conn.execute(
                """INSERT INTO auscultation_recordings (crew_id, mission_stage, organ_type,
                   anatomical_site, duration_sec, cabin_noise_dba, file_rel_path, sha256_hex,
                   findings_json, recorded_at_utc)
                   VALUES (?, 'MISSION', ?, ?, 30, ?, ?, ?, ?, ?)""",
                (
                    plan.crew_id,
                    organ,
                    site,
                    48.0,
                    f"audio/{name}",
                    hashlib.sha256(data).hexdigest(),
                    json.dumps(findings),
                    _ts(at + timedelta(minutes=index)),
                ),
            )


def _seed_comms_and_checks(conn: sqlite3.Connection, launch: datetime, now: datetime) -> None:
    today = _day_start(launch, MISSION_DAY_TODAY)

    def at(hours: float) -> datetime:
        return _clamp_to_now(today + timedelta(hours=hours), now)

    directives = (
        (
            "Daily Biomedical Review - Day 047",
            "Dr. R. Miller · Flight Surgeon",
            "Right optic sheath trend noted for E. Vargas. Continue evening lower-body negative "
            "pressure and +400 mL hydration today. All other crew vitals nominal.",
            at(13.75),
            "ID-01",
        ),
        (
            "Post-EVA Recovery - J. Reed",
            "Medical Operations",
            "Heart rate and hydration recovery progressing on schedule following exterior "
            "maintenance shift. Cleared for standard interior duty tomorrow.",
            at(8.33),
            "ID-04",
        ),
        (
            "Habitat A Air Quality Summary",
            "Environmental Desk",
            "24-hour cabin CO2 averaged 2.8 mmHg with 44% relative humidity. Sleep station airflow "
            "settings approved for current transit phase.",
            today - timedelta(hours=16),
            None,
        ),
    )
    for title, sender, guidance, sent, crew in directives:
        conn.execute(
            """INSERT INTO ground_outbox (packet_type, direction, crew_id, bundle_json,
               created_at_utc, deliver_after_utc, delivered_at_utc, status)
               VALUES ('GROUND_DIRECTIVE', 'INBOUND', ?, ?, ?, ?, ?, 'ACKNOWLEDGED')""",
            (
                crew,
                json.dumps({"title_en": title, "sender_en": sender, "guidance_en": guidance}),
                _ts(sent - timedelta(minutes=12)),
                _ts(sent),
                _ts(sent),
            ),
        )
    outbound = (
        ("DAILY_SUMMARY", "Crew Daily Readiness Summary", today + timedelta(hours=14)),
        ("CLINICAL_REPORT", "Ocular Exam Update (E. Vargas)", today + timedelta(hours=12.5)),
        ("CLINICAL_REPORT", "Morning Auscultation & Vitals Log", today + timedelta(hours=8.25)),
        ("DAILY_SUMMARY", "Crew Daily Readiness Summary", today - timedelta(hours=10)),
    )
    for packet_type, title, sent in outbound:
        if sent + timedelta(minutes=24) > now:
            continue  # only packets whose round trip has already completed
        conn.execute(
            """INSERT INTO ground_outbox (packet_type, direction, crew_id, bundle_json,
               created_at_utc, deliver_after_utc, delivered_at_utc, status)
               VALUES (?, 'OUTBOUND', NULL, ?, ?, ?, ?, 'ACKNOWLEDGED')""",
            (
                packet_type,
                json.dumps({"title_en": title}),
                _ts(sent),
                _ts(sent + timedelta(minutes=12)),
                _ts(sent + timedelta(minutes=12)),
            ),
        )
    # Follow-up eye scan asked for by the physician after the Day 047 exam.
    conn.execute(
        """INSERT INTO scheduled_checks (crew_id, check_type, title_en, due_at_utc, status,
           created_at_utc) VALUES ('ID-01', 'OCULAR_EXAM',
           'Bilateral optic nerve ultrasound follow-up', ?, 'PENDING', ?)""",
        (_ts(today + timedelta(days=3, hours=11)), _ts(now)),
    )
    refresh_scheduled_checks(conn, now=now)


def _evaluate_and_settle(conn: sqlite3.Connection, w: Writer, now: datetime) -> None:
    """Run the alert engine over every mission reading; older advisories were already handled."""
    for measurement_id in sorted(
        w.pending,
        key=lambda i: conn.execute(
            "SELECT recorded_at_utc FROM measurements WHERE id = ?", (i,)
        ).fetchone()[0],
    ):
        for alert_id in evaluate_alerts(conn, measurement_id):
            taken = conn.execute(
                "SELECT m.recorded_at_utc, m.crew_id FROM alerts a JOIN measurements m "
                "ON m.id = a.measurement_id WHERE a.id = ?",
                (alert_id,),
            ).fetchone()
            conn.execute(
                "UPDATE alerts SET created_at_utc = ? WHERE id = ?",
                (taken["recorded_at_utc"], alert_id),
            )
            moment = datetime.fromisoformat(taken["recorded_at_utc"].replace("Z", "+00:00"))
            if now - moment > timedelta(hours=24):
                conn.execute(
                    "UPDATE alerts SET acknowledged_at_utc = ?, acknowledged_by = ? WHERE id = ?",
                    (_ts(moment + timedelta(hours=2)), taken["crew_id"], alert_id),
                )


def seed_database(
    db_path: Path = DB_PATH,
    schema_path: Path = SCHEMA_PATH,
    snapshot_path: Path = SEED_SNAPSHOT_PATH,
    audio_dir: Path = AUDIO_STORAGE_DIR,
    with_audio: bool = True,
) -> dict[str, int]:
    """Create the schema and load the 47-day training mission (only into an empty database)."""
    template = os.environ.get("SPACESCAN_SEED_TEMPLATE")
    if template and Path(template).exists() and not Path(db_path).exists():
        # Test runs reuse one prepared mission instead of rebuilding it for every test.
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template, db_path)
    init_db(db_path=db_path, schema_path=schema_path)
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    # Today is always Day 047; anything planned later today is placed just before now.
    now = datetime.now(UTC).replace(microsecond=0)
    launch = datetime.combine(
        now.date() - timedelta(days=MISSION_DAY_TODAY - 1), time(8, 0), tzinfo=UTC
    )
    rng = random.Random(2026)

    with open_connection(db_path) as conn:
        if conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == 0:
            _seed_reference_rows(conn, snapshot, launch, now)
            writer = Writer(conn)
            for plan in PLANS:
                _seed_crew(conn, writer, plan, launch, now, rng)
                compute_crew_baselines(conn, plan.crew_id)
            _seed_environment(conn, launch, now, rng)
            if with_audio:
                audio_dir.mkdir(parents=True, exist_ok=True)
                for plan in PLANS:
                    _seed_auscultation(conn, plan, launch, now, audio_dir)
            _seed_comms_and_checks(conn, launch, now)
            _evaluate_and_settle(conn, writer, now)
            for plan in PLANS:
                for day in range(1 - PRE_FLIGHT_DAYS, MISSION_DAY_TODAY + 1):
                    recompute_day(conn, plan.crew_id, _day_start(launch, day).date().isoformat())
        else:
            load_medical_guide(conn)

        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "crew_members",
                "metric_catalog",
                "measurements",
                "sleep_sessions",
                "wiki_articles",
                "alerts",
                "auscultation_recordings",
            )
        }


def reset_database(db_path: Path = DB_PATH) -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset_database()
    print("Seed completed:", json.dumps(seed_database()))
