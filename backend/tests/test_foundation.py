"""Schema integrity, append-only health records and the seeded training mission."""

import sqlite3

import pytest

from app.services import reference_ranges
from app.services.mission_clock import mission_day

APPEND_ONLY = (
    "measurements",
    "sleep_sessions",
    "sleep_stages",
    "psych_tests",
    "cognitive_tests",
    "auscultation_recordings",
    "review_decisions",
)


def test_schema_is_strict_and_idempotent(db):
    from app.db import init_db, resolve_db_path

    init_db(resolve_db_path())  # applying the schema twice changes nothing
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {
        "mission",
        "crew_members",
        "metric_catalog",
        "baselines",
        "measurements",
        "environment_readings",
        "streak_days",
        "ground_outbox",
        "sleep_sessions",
        "sleep_stages",
        "auscultation_recordings",
        "wiki_articles",
        "psych_tests",
        "cognitive_tests",
        "scheduled_checks",
        "alerts",
        "diagnoses",
    } <= tables
    assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


@pytest.mark.parametrize("table", APPEND_ONLY)
def test_health_records_are_append_only(db, table):
    if db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0:
        pytest.skip("no rows seeded for this table")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(f"DELETE FROM {table}")
    column = db.execute(f"PRAGMA table_info({table})").fetchall()[1][1]
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(f"UPDATE {table} SET {column} = {column}")


def test_catalog_matches_reference_ranges(db):
    rows = {r["metric_key"]: r for r in db.execute("SELECT * FROM metric_catalog")}
    reference = reference_ranges.load_reference()["metrics"]
    assert set(rows) == {m["metric_key"] for m in reference}
    for metric in reference:
        row = rows[metric["metric_key"]]
        for field in (
            "nominal_min",
            "nominal_max",
            "warning_min",
            "warning_max",
            "critical_min",
            "critical_threshold",
        ):
            assert row[field] == metric[field], (metric["metric_key"], field)
        assert row["clinical_reference"]


def test_research_reference_values():
    """Limits taken from the team's research parameters."""
    limits = reference_ranges.thresholds
    assert (limits("resting_hr_bpm").nominal_min, limits("resting_hr_bpm").nominal_max) == (40, 100)
    assert (
        limits("bp_systolic_mmhg").nominal_max == 119
        and limits("bp_diastolic_mmhg").nominal_max == 79
    )
    assert (limits("body_temp_c").nominal_min, limits("body_temp_c").nominal_max) == (36.5, 37.3)
    assert limits("spo2_pct").nominal_min == 95 and limits("spo2_pct").warning_min == 93
    assert (
        limits("blood_glucose_mg_dl").nominal_min,
        limits("blood_glucose_mg_dl").nominal_max,
    ) == (70, 99)
    assert (limits("bmi_kg_m2").nominal_min, limits("bmi_kg_m2").nominal_max) == (18.5, 24.9)
    assert limits("bmi_kg_m2").critical_threshold == 28
    assert (limits("cabin_temp_c").nominal_min, limits("cabin_temp_c").nominal_max) == (20, 25)
    assert (limits("cabin_humidity_pct").nominal_min, limits("cabin_humidity_pct").nominal_max) == (
        30,
        60,
    )
    assert (
        limits("urine_color_scale").nominal_max == 3
        and limits("urine_color_scale").critical_threshold == 7
    )
    sleep = reference_ranges.sleep_reference()
    assert sleep["total_min"]["nominal"] == [420, 540]
    assert sleep["deep_pct"] == [15, 25] and sleep["rem_pct"] == [20, 25]


@pytest.mark.parametrize(
    "value, expected",
    [
        (98, "NOMINAL"),
        (94, "WATCH"),
        (92, "WARNING"),
        (90, "CRITICAL"),
    ],
)
def test_oxygen_bands(value, expected):
    assert reference_ranges.status_label("spo2_pct", value) == expected


@pytest.mark.parametrize(
    "systolic, expected",
    [
        (118, "NOMINAL"),
        (125, "WATCH"),
        (135, "WATCH"),
        (145, "WARNING"),
        (185, "CRITICAL"),
    ],
)
def test_blood_pressure_bands(systolic, expected):
    assert reference_ranges.status_label("bp_systolic_mmhg", systolic) == expected


def test_relative_rules_follow_research():
    relative = reference_ranges.classify_relative
    assert relative("vo2_max_ml_kg_min", 39, 50).name == "WARNING"  # under 80% of pre-flight
    assert relative("vo2_max_ml_kg_min", 46, 50) is None
    assert relative("bone_density_g_cm2", 1.12, 1.20).name == "CRITICAL"  # more than 6.2% lost
    assert relative("body_weight_kg", 61, 70).name == "CRITICAL"  # under 90% retained


def test_personal_targets_use_sex_age_and_mass():
    woman = reference_ranges.personal_targets({"sex": "F", "age": 36, "height_cm": 171}, 64.0)
    man = reference_ranges.personal_targets({"sex": "M", "age": 39, "height_cm": 182}, 79.0)
    assert 2000 <= woman.hydration_ml <= 2700 and 2500 <= man.hydration_ml <= 3700
    assert woman.calories_kcal == 2000 and man.calories_kcal == 2500
    assert woman.muscle_mass_kg == (18, 24) and man.muscle_mass_kg == (28, 36)
    assert woman.exercise_min == 30


def test_seed_builds_day_47_with_real_baselines(db):
    assert mission_day(db) in (47, 48)  # 48 before the afternoon check-in of the next day
    assert db.execute("SELECT COUNT(*) FROM crew_members").fetchone()[0] == 4
    names = [r[0] for r in db.execute("SELECT full_name FROM crew_members ORDER BY code")]
    assert names == ["Elena Vargas", "Marcus Vance", "Amara Okafor", "Jonas Reed"]
    row = db.execute(
        "SELECT mean_val, std_dev, sample_count FROM baselines "
        "WHERE crew_id = 'ID-01' AND metric_key = 'body_temp_c'"
    ).fetchone()
    assert row["sample_count"] == 7 and 36.5 <= row["mean_val"] <= 36.9
    assert row["std_dev"] < 0.4  # a real spread, so a fever shows as drift


def test_seed_stories_produce_expected_open_advisories(db):
    def open_alerts(crew_id):
        return db.execute(
            "SELECT severity, title_en FROM alerts "
            "WHERE crew_id = ? AND acknowledged_at_utc IS NULL",
            (crew_id,),
        ).fetchall()

    elena = open_alerts("ID-01")
    assert any(
        a["severity"] == "CRITICAL" and "Right Optic Nerve Sheath" in a["title_en"] for a in elena
    )
    assert any("hydration goal" in a["title_en"] for a in elena)
    assert not any(
        a["severity"] == "CRITICAL" for c in ("ID-02", "ID-03", "ID-04") for a in open_alerts(c)
    )
    assert open_alerts("ID-03") == []  # the physician's own readings are all in range
    total = db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    assert total < 200  # 47 days x 4 crew without alert noise


def test_seed_is_idempotent(db, temp_db_path):
    from db.seed import seed_database

    before = db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
    seed_database(db_path=temp_db_path, with_audio=False)
    assert db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == before


def test_sensor_simulator_stays_near_the_logged_values(db):
    import random

    from app.services.sensor_simulator import run_sensor_tick

    rng = random.Random(1)
    for _ in range(200):  # more than half a day of readings
        run_sensor_tick(db, rng)
    rows = db.execute(
        "SELECT MIN(value_num), MAX(value_num) FROM measurements WHERE crew_id = 'ID-03' "
        "AND metric_key = 'body_temp_c' AND source_type = 'AUTO'"
    ).fetchone()
    assert 36.4 <= rows[0] and rows[1] <= 37.0
    temps = db.execute(
        "SELECT temp_c FROM environment_readings ORDER BY recorded_at_utc DESC LIMIT 200"
    ).fetchall()
    assert all(20 <= r[0] <= 24 for r in temps)
    noisy = db.execute(
        "SELECT COUNT(*) FROM alerts WHERE crew_id = 'ID-03' AND acknowledged_at_utc IS NULL"
    ).fetchone()[0]
    assert noisy == 0
