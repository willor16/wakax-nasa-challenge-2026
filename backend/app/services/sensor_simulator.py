"""Onboard sensor simulator (architecture: "Python sensor simulator", core).

Stands in for the wearable and cabin sensors during demonstrations: it writes
AUTO-sourced readings that follow each crew member's latest logged values, and
an ECG Lead II strip consistent with the current heart rate. Every value then
goes through the same ingestion path (alerts, streaks) as a real sensor would.
Disable with ``SPACESCAN_SENSOR_SIMULATOR=0``.
"""

from __future__ import annotations

import json
import math
import os
import random
import sqlite3

from app.services.mission_clock import current_stage, to_iso, utc_now

ECG_SAMPLE_RATE_HZ = 125
ECG_SECONDS = 6


def simulator_enabled() -> bool:
    return os.environ.get("SPACESCAN_SENSOR_SIMULATOR", "1") != "0"


def ecg_strip(
    heart_rate_bpm: float,
    seconds: int = ECG_SECONDS,
    sample_rate: int = ECG_SAMPLE_RATE_HZ,
    seed: int = 0,
) -> list[float]:
    """Lead II strip built from P, QRS and T waves (Gaussian model) in millivolts."""
    rng = random.Random(seed)
    beat = 60.0 / max(30.0, heart_rate_bpm)
    waves = (
        (-0.20, 0.025, 0.12),
        (-0.03, 0.010, -0.12),
        (0.0, 0.012, 1.25),
        (0.03, 0.010, -0.22),
        (0.26, 0.045, 0.30),
    )
    samples: list[float] = []
    beat_starts: list[float] = []
    t = 0.25
    while t < seconds + beat:
        beat_starts.append(t)
        t += beat * (1 + rng.gauss(0, 0.015))
    for i in range(seconds * sample_rate):
        now = i / sample_rate
        value = 0.0
        for start in beat_starts:
            offset = now - start
            if -0.4 < offset < 0.5:
                for centre, width, amp in waves:
                    value += amp * math.exp(-((offset - centre) ** 2) / (2 * width**2))
        samples.append(round(value + rng.gauss(0, 0.01), 3))
    return samples


def ecg_payload(heart_rate_bpm: float, seed: int = 0) -> dict:
    return {
        "lead": "II",
        "sample_rate_hz": ECG_SAMPLE_RATE_HZ,
        "paper_speed_mm_s": 25,
        "samples": ecg_strip(heart_rate_bpm, seed=seed),
    }


def _latest(conn: sqlite3.Connection, crew_id: str, metric_key: str) -> float | None:
    """Latest reading logged by the crew: the simulated sensor follows it, never itself."""
    row = conn.execute(
        """SELECT value_num FROM measurements WHERE crew_id = ? AND metric_key = ?
           AND value_num IS NOT NULL AND source_type = 'MANUAL'
           ORDER BY recorded_at_utc DESC, id DESC LIMIT 1""",
        (crew_id, metric_key),
    ).fetchone()
    return float(row["value_num"]) if row else None


def run_sensor_tick(conn: sqlite3.Connection, rng: random.Random | None = None) -> int:
    """Write one round of wearable and cabin readings. Returns readings written."""
    from app.services.contracts import evaluate_alerts

    rng = rng or random.Random()
    now = to_iso(utc_now())
    stage = current_stage(conn)
    written = 0
    crew = conn.execute("SELECT id FROM crew_members WHERE is_active = 1").fetchall()
    for member in crew:
        crew_id = member["id"]
        hr = _latest(conn, crew_id, "resting_hr_bpm")
        spo2 = _latest(conn, crew_id, "spo2_pct")
        temp = _latest(conn, crew_id, "body_temp_c")
        readings: list[tuple[str, float, dict]] = []
        if hr is not None:
            live_hr = round(hr + rng.gauss(0, 1.2))
            readings.append(
                (
                    "ecg_lead_ii_mv",
                    1.2,
                    ecg_payload(live_hr, seed=rng.randint(0, 9999)) | {"heart_rate_bpm": live_hr},
                )
            )
        if spo2 is not None:
            readings.append(("spo2_pct", round(min(100.0, spo2 + rng.gauss(0, 0.3))), {}))
        if temp is not None:
            readings.append(("body_temp_c", round(temp + rng.gauss(0, 0.05), 1), {}))
        for metric_key, value, payload in readings:
            cursor = conn.execute(
                """INSERT INTO measurements (crew_id, metric_key, mission_stage, source_type,
                   recorded_at_utc, value_num, payload_json) VALUES (?, ?, ?, 'AUTO', ?, ?, ?)""",
                (crew_id, metric_key, stage, now, value, json.dumps(payload)),
            )
            evaluate_alerts(conn, int(cursor.lastrowid))
            written += 1

    # Cabin values hover around the average of the last day, so they cannot wander off.
    last = conn.execute(
        """SELECT AVG(co2_ppm) AS co2_ppm, AVG(noise_dba) AS noise_dba, AVG(temp_c) AS temp_c,
                  AVG(humidity_pct) AS humidity_pct, MAX(recorded_at_utc) AS recorded_at_utc
           FROM environment_readings WHERE recorded_at_utc >= (
               SELECT datetime(MAX(recorded_at_utc), '-1 day') FROM environment_readings)"""
    ).fetchone()
    latest = conn.execute(
        "SELECT * FROM environment_readings ORDER BY recorded_at_utc DESC, id DESC LIMIT 1"
    ).fetchone()
    if latest is not None and last["co2_ppm"] is not None:
        from app.services.environment import record_reading

        record_reading(
            conn,
            {
                "co2_ppm": round(max(2000.0, last["co2_ppm"] + rng.gauss(0, 60))),
                "noise_dba": round(last["noise_dba"] + rng.gauss(0, 0.4), 1),
                "temp_c": round(last["temp_c"] + rng.gauss(0, 0.1), 1),
                "humidity_pct": round(
                    min(70.0, max(30.0, last["humidity_pct"] + rng.gauss(0, 0.3))), 1
                ),
                "radiation_msv": latest["radiation_msv"],
                "solar_event": bool(latest["solar_event_flag"]),
                "kp_index": latest["kp_index"],
                "location_en": latest["location_en"],
                "recorded_at_utc": now,
            },
        )
        written += 1
    return written


def run_sensor_tick_job() -> None:
    """APScheduler entry point."""
    if not simulator_enabled():
        return
    from app.deps import open_request_connection

    with open_request_connection() as conn:
        run_sensor_tick(conn)
