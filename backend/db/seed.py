"""Pre-flight and offline snapshot database seeder for SpaceScan."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.auth_utils import hash_pin
from app.config import DB_PATH, SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import init_db, open_connection
from app.services.contracts import evaluate_alerts
from app.services.wiki_seed import load_medical_guide


def seed_database(
    db_path: Path = DB_PATH,
    schema_path: Path = SCHEMA_PATH,
    snapshot_path: Path = SEED_SNAPSHOT_PATH,
) -> dict[str, int]:
    """Initialize schema and load offline mission snapshot idempotently."""
    init_db(db_path=db_path, schema_path=schema_path)
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open_connection(db_path) as conn:
        existing_mission = conn.execute("SELECT id FROM mission WHERE id = 1").fetchone()
        if existing_mission is None:
            m = snapshot["mission"]
            conn.execute(
                """
                INSERT INTO mission (
                    id, mission_code, mission_name, current_stage, launch_utc,
                    planned_return_utc, earth_latency_min, quiet_hours_start_utc,
                    quiet_hours_end_utc, updated_at_utc
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    m["mission_code"],
                    m["mission_name"],
                    m["current_stage"],
                    m["launch_utc"],
                    m["planned_return_utc"],
                    m["earth_latency_min"],
                    m["quiet_hours_start_utc"],
                    m["quiet_hours_end_utc"],
                    now_utc,
                ),
            )

        for member in snapshot["crew_members"]:
            conn.execute(
                """
                INSERT OR IGNORE INTO crew_members (
                    id, code, full_name, role, pin_hash, age, sex, blood_type,
                    height_cm, is_active, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
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
                    now_utc,
                    now_utc,
                ),
            )

        for metric in snapshot["metric_catalog"]:
            conn.execute(
                """
                INSERT OR IGNORE INTO metric_catalog (
                    metric_key, display_name_en, category, unit, nominal_min, nominal_max,
                    warning_min, warning_max, critical_min, critical_threshold,
                    recommended_frequency_hours, clinical_reference
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metric["metric_key"],
                    metric["display_name_en"],
                    metric["category"],
                    metric["unit"],
                    metric["nominal_min"],
                    metric["nominal_max"],
                    metric["warning_min"],
                    metric["warning_max"],
                    metric["critical_min"],
                    metric["critical_threshold"],
                    metric["recommended_frequency_hours"],
                    metric["clinical_reference"],
                ),
            )

        for article in snapshot["wiki_articles"]:
            conn.execute(
                """
                INSERT OR IGNORE INTO wiki_articles (
                    id, category_en, title_en, drawer_code, steps_json,
                    escalation_en, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article["id"],
                    article["category_en"],
                    article["title_en"],
                    article["drawer_code"],
                    json.dumps(article["steps_json"]),
                    article["escalation_en"],
                    now_utc,
                    now_utc,
                ),
            )

        if conn.execute("SELECT COUNT(*) FROM environment_readings").fetchone()[0] == 0:
            for env in snapshot["environment_readings"]:
                conn.execute(
                    """
                    INSERT INTO environment_readings (
                        co2_ppm, noise_dba, temp_c, humidity_pct,
                        radiation_msv, solar_event_flag, recorded_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        env["co2_ppm"],
                        env["noise_dba"],
                        env["temp_c"],
                        env["humidity_pct"],
                        env["radiation_msv"],
                        env["solar_event_flag"],
                        env["recorded_at_utc"],
                    ),
                )

        load_medical_guide(conn)  # Dev 3: guide articles and medical kit (D3-06)

        if conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == 0:
            _seed_crew_clinical_history(conn)

        conn.commit()
        return {
            "crew_members": conn.execute("SELECT COUNT(*) FROM crew_members").fetchone()[0],
            "metric_catalog": conn.execute("SELECT COUNT(*) FROM metric_catalog").fetchone()[0],
            "measurements": conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0],
            "wiki_articles": conn.execute("SELECT COUNT(*) FROM wiki_articles").fetchone()[0],
            "alerts": conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
        }


def _seed_crew_clinical_history(conn: sqlite3.Connection) -> None:
    """Populate pre-flight baselines, longitudinal measurements, sleep, psych, and outbox."""
    base_time = datetime(2026, 11, 14, 14, 0, 0, tzinfo=UTC)
    launch_time = datetime(2026, 10, 1, 6, 0, 0, tzinfo=UTC)

    crew_profiles = {
        "ID-01": {
            "resting_hr_bpm": (62.0, 64.0),
            "hrv_rmssd_ms": (64.0, 58.0),
            "spo2_pct": (98.5, 98.0),
            "bp_systolic_mmhg": (114.0, 118.0),
            "body_temp_c": (36.6, 36.7),
            "body_weight_kg": (63.5, 62.9),
            "muscle_mass_retention_pct": (100.0, 97.5),
            "bone_density_tscore": (0.4, 0.2),
            "vo2_max_ml_kg_min": (48.0, 46.5),
            "optic_sheath_left_mm": (4.2, 4.5),
            "optic_sheath_right_mm": (4.3, 5.2),
            "iop_left_mmhg": (14.0, 16.0),
            "iop_right_mmhg": (14.5, 17.5),
            "blood_glucose_mg_dl": (88.0, 92.0),
            "hydration_ml": (2600.0, 2450.0),
            "exercise_min": (90.0, 85.0),
            "calories_kcal": (2450.0, 2400.0),
        },
        "ID-02": {
            "resting_hr_bpm": (58.0, 60.0),
            "hrv_rmssd_ms": (70.0, 68.0),
            "spo2_pct": (99.0, 98.4),
            "bp_systolic_mmhg": (118.0, 120.0),
            "body_temp_c": (36.5, 36.6),
            "body_weight_kg": (79.0, 78.4),
            "muscle_mass_retention_pct": (100.0, 98.6),
            "bone_density_tscore": (0.7, 0.6),
            "vo2_max_ml_kg_min": (52.0, 51.0),
            "optic_sheath_left_mm": (4.1, 4.3),
            "optic_sheath_right_mm": (4.1, 4.4),
            "iop_left_mmhg": (15.0, 15.5),
            "iop_right_mmhg": (15.0, 16.0),
            "blood_glucose_mg_dl": (91.0, 94.0),
            "hydration_ml": (2900.0, 2850.0),
            "exercise_min": (105.0, 95.0),
            "calories_kcal": (2850.0, 2800.0),
        },
        "ID-03": {
            "resting_hr_bpm": (65.0, 66.0),
            "hrv_rmssd_ms": (60.0, 59.0),
            "spo2_pct": (98.0, 98.2),
            "bp_systolic_mmhg": (112.0, 114.0),
            "body_temp_c": (36.7, 36.7),
            "body_weight_kg": (60.0, 59.8),
            "muscle_mass_retention_pct": (100.0, 98.2),
            "bone_density_tscore": (0.3, 0.25),
            "vo2_max_ml_kg_min": (45.0, 44.5),
            "optic_sheath_left_mm": (4.0, 4.2),
            "optic_sheath_right_mm": (4.0, 4.2),
            "iop_left_mmhg": (13.5, 14.0),
            "iop_right_mmhg": (13.5, 14.0),
            "blood_glucose_mg_dl": (86.0, 88.0),
            "hydration_ml": (2500.0, 2550.0),
            "exercise_min": (80.0, 80.0),
            "calories_kcal": (2250.0, 2280.0),
        },
        "ID-04": {
            "resting_hr_bpm": (61.0, 68.0),
            "hrv_rmssd_ms": (66.0, 49.0),
            "spo2_pct": (98.8, 97.5),
            "bp_systolic_mmhg": (116.0, 122.0),
            "body_temp_c": (36.6, 36.8),
            "body_weight_kg": (72.0, 70.9),
            "muscle_mass_retention_pct": (100.0, 96.8),
            "bone_density_tscore": (0.5, 0.35),
            "vo2_max_ml_kg_min": (49.5, 47.0),
            "optic_sheath_left_mm": (4.2, 4.6),
            "optic_sheath_right_mm": (4.3, 4.7),
            "iop_left_mmhg": (14.5, 16.0),
            "iop_right_mmhg": (14.5, 16.5),
            "blood_glucose_mg_dl": (90.0, 96.0),
            "hydration_ml": (2700.0, 2300.0),
            "exercise_min": (95.0, 75.0),
            "calories_kcal": (2650.0, 2450.0),
        },
    }

    launch_ts = launch_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    mission_ts = base_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    for crew_id, metrics in crew_profiles.items():
        for metric_key, (baseline_val, mission_val) in metrics.items():
            conn.execute(
                """
                INSERT INTO baselines (
                    crew_id, metric_key, mean_val, std_dev, sample_count, computed_at_utc
                ) VALUES (?, ?, ?, ?, 5, ?)
                """,
                (crew_id, metric_key, baseline_val, round(max(baseline_val * 0.04, 0.2), 3), launch_ts),
            )
            conn.execute(
                """
                INSERT INTO measurements (
                    crew_id, metric_key, mission_stage, source_type,
                    recorded_at_utc, value_num, payload_json
                ) VALUES (?, ?, 'LAUNCH', 'MANUAL', ?, ?, '{}')
                """,
                (crew_id, metric_key, launch_ts, baseline_val),
            )
            cur = conn.execute(
                """
                INSERT INTO measurements (
                    crew_id, metric_key, mission_stage, source_type,
                    recorded_at_utc, value_num, payload_json
                ) VALUES (?, ?, 'MISSION', 'MANUAL', ?, ?, '{}')
                """,
                (crew_id, metric_key, mission_ts, mission_val),
            )
            evaluate_alerts(conn, int(cur.lastrowid))

        for offset in range(7):
            day_str = (base_time - timedelta(days=offset)).strftime("%Y-%m-%d")
            conn.execute(
                """
                INSERT INTO streak_days (
                    crew_id, streak_date_utc, logs_completed, habits_met,
                    daily_compliant, updated_at_utc
                ) VALUES (?, ?, 3, 1, 1, ?)
                """,
                (crew_id, day_str, mission_ts),
            )

        sleep_start = (base_time - timedelta(hours=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
        sleep_end = (base_time - timedelta(hours=6, minutes=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
        sleep_cur = conn.execute(
            """
            INSERT INTO sleep_sessions (
                crew_id, mission_stage, sleep_start_utc, sleep_end_utc,
                total_sleep_min, time_in_bed_min, sleep_score, sleep_efficiency_pct,
                deep_min, rem_min, light_min, awake_min, recorded_at_utc
            ) VALUES (?, 'MISSION', ?, ?, 432, 468, 84, 92.3, 94, 102, 236, 36, ?)
            """,
            (crew_id, sleep_start, sleep_end, sleep_end),
        )
        session_id = int(sleep_cur.lastrowid)
        stages = [
            ("LIGHT", 0, 42),
            ("DEEP", 42, 136),
            ("REM", 136, 188),
            ("AWAKE", 188, 204),
            ("LIGHT", 204, 340),
            ("REM", 340, 390),
            ("LIGHT", 390, 448),
            ("AWAKE", 448, 468),
        ]
        t0 = base_time - timedelta(hours=14)
        for stage_name, start_m, end_m in stages:
            s_ts = (t0 + timedelta(minutes=start_m)).strftime("%Y-%m-%dT%H:%M:%SZ")
            e_ts = (t0 + timedelta(minutes=end_m)).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute(
                """
                INSERT INTO sleep_stages (session_id, stage, start_utc, end_utc, duration_min)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, stage_name, s_ts, e_ts, end_m - start_m),
            )

        conn.execute(
            """
            INSERT INTO psych_tests (
                crew_id, mission_stage, mood_score, stress_score, loneliness_score,
                motivation_score, wellbeing_index, notes_en, recorded_at_utc
            ) VALUES (?, 'MISSION', 4, 2, 2, 5, 84.0, 'Routine transit check-in nominal.', ?)
            """,
            (crew_id, mission_ts),
        )
        conn.execute(
            """
            INSERT INTO cognitive_tests (
                crew_id, mission_stage, test_type, reaction_ms, accuracy_pct,
                attention_score, duration_sec, recorded_at_utc
            ) VALUES (?, 'MISSION', 'REACTION_ARENA', 268.0, 96.5, 94.0, 120, ?)
            """,
            (crew_id, mission_ts),
        )
        conn.execute(
            """
            INSERT INTO scheduled_checks (
                crew_id, check_type, title_en, due_at_utc, status, created_at_utc
            ) VALUES (?, 'OCULAR_EXAM', 'Bilateral Optic Nerve Ultrasound', ?, 'PENDING', ?)
            """,
            (crew_id, (base_time + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ"), mission_ts),
        )

    outbox_bundle = {
        "mission_code": "ARES VII",
        "mission_stage": "MISSION",
        "generated_at_utc": mission_ts,
        "crew_summary": "4 active crew members; 1 ocular warning flagged for routine review.",
    }
    conn.execute(
        """
        INSERT INTO ground_outbox (
            packet_type, direction, crew_id, bundle_json,
            created_at_utc, deliver_after_utc, status
        ) VALUES ('DAILY_SUMMARY', 'OUTBOUND', 'ID-01', ?, ?, ?, 'QUEUED')
        """,
        (
            json.dumps(outbox_bundle),
            mission_ts,
            (base_time + timedelta(minutes=12)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )


if __name__ == "__main__":
    summary = seed_database()
    print("Seed completed:", json.dumps(summary))
