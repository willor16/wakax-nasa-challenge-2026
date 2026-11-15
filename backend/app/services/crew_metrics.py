"""Shared crew baseline calculation and readiness scoring services."""

import math
import sqlite3
from datetime import UTC, datetime
from typing import Any

from app.services.reference_ranges import sleep_reference


def compute_crew_baselines(conn: sqlite3.Connection, crew_id: str) -> list[dict[str, Any]]:
    """Compute mean and standard deviation from LAUNCH measurements and upsert baselines."""
    rows = conn.execute(
        """
        SELECT metric_key, value_num
        FROM measurements
        WHERE crew_id = ? AND mission_stage = 'LAUNCH' AND value_num IS NOT NULL
        ORDER BY metric_key ASC, id ASC
        """,
        (crew_id,),
    ).fetchall()

    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(row["metric_key"], []).append(float(row["value_num"]))

    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    results: list[dict[str, Any]] = []

    for metric_key, values in grouped.items():
        n = len(values)
        mean_val = sum(values) / n
        if n > 1:
            variance = sum((v - mean_val) ** 2 for v in values) / (n - 1)
            std_dev = round(math.sqrt(variance), 4)
        else:
            std_dev = 0.0  # one reading has no spread; drift checks need 3 or more

        mean_rounded = round(mean_val, 4)
        conn.execute(
            """
            INSERT INTO baselines (
                crew_id, metric_key, mean_val, std_dev, sample_count, computed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(crew_id, metric_key) DO UPDATE SET
                mean_val = excluded.mean_val,
                std_dev = excluded.std_dev,
                sample_count = excluded.sample_count,
                computed_at_utc = excluded.computed_at_utc
            """,
            (crew_id, metric_key, mean_rounded, std_dev, n, now_utc),
        )
        results.append(
            {
                "crew_id": crew_id,
                "metric_key": metric_key,
                "mean_val": mean_rounded,
                "std_dev": std_dev,
                "sample_count": n,
                "computed_at_utc": now_utc,
            }
        )

    return results


def _latest_metric(conn: sqlite3.Connection, crew_id: str, metric_key: str) -> float | None:
    row = conn.execute(
        """
        SELECT value_num
        FROM measurements
        WHERE crew_id = ? AND metric_key = ? AND value_num IS NOT NULL
        ORDER BY recorded_at_utc DESC, id DESC
        LIMIT 1
        """,
        (crew_id, metric_key),
    ).fetchone()
    return float(row["value_num"]) if row else None


def evaluate_crew_readiness(conn: sqlite3.Connection, crew_id: str) -> dict[str, Any]:
    """Readiness score, status (Optimal / Nominal / Attention) and key vitals.

    The status follows the open health advisories and last night's sleep:
    * Attention - an open WARNING or CRITICAL clinical advisory, or under 6 h of sleep.
    * Nominal   - an open drift notice (INFO), or sleep under the 7 h target.
    * Optimal   - none of the above.
    Daily habit reminders (water, meals, exercise) do not change the clinical status.
    """
    alerts = conn.execute(
        """
        SELECT severity, category FROM alerts
        WHERE crew_id = ? AND acknowledged_at_utc IS NULL
        """,
        (crew_id,),
    ).fetchall()
    clinical = [a for a in alerts if a["category"] != "HABITS"]
    critical_count = sum(1 for a in clinical if a["severity"] == "CRITICAL")
    warning_count = sum(1 for a in clinical if a["severity"] == "WARNING")
    info_count = sum(1 for a in clinical if a["severity"] == "INFO")

    hr = _latest_metric(conn, crew_id, "resting_hr_bpm")
    hrv = _latest_metric(conn, crew_id, "hrv_rmssd_ms")
    spo2 = _latest_metric(conn, crew_id, "spo2_pct")

    sleep_row = conn.execute(
        """
        SELECT total_sleep_min, sleep_score
        FROM sleep_sessions
        WHERE crew_id = ?
        ORDER BY sleep_end_utc DESC, id DESC
        LIMIT 1
        """,
        (crew_id,),
    ).fetchone()
    sleep_min = int(sleep_row["total_sleep_min"]) if sleep_row else None
    sleep_score = int(sleep_row["sleep_score"]) if sleep_row else None
    sleep_ref = sleep_reference()["total_min"]
    sleep_target = sleep_ref["nominal"][0]
    sleep_floor = sleep_ref["warning"][0]

    score = 100.0
    score -= critical_count * 12 + warning_count * 6 + min(info_count, 4) * 2
    if sleep_score is not None:
        score -= max(0, 85 - sleep_score) * 0.4
    score = int(max(0, min(100, round(score))))

    short_sleep = sleep_min is not None and sleep_min < sleep_floor
    below_target = sleep_min is not None and sleep_min < sleep_target
    if critical_count or warning_count or short_sleep:
        status_label = "Attention"
    elif info_count or below_target:
        status_label = "Nominal"
    else:
        status_label = "Optimal"

    return {
        "status": status_label,
        "readiness_score": score,
        "unread_alerts": len(alerts),
        "advisories": critical_count + warning_count,
        "vitals": {
            "resting_hr_bpm": hr,
            "hrv_rmssd_ms": hrv,
            "spo2_pct": spo2,
            "sleep_min_24h": sleep_min,
            "sleep_hours_24h": round(sleep_min / 60.0, 1) if sleep_min is not None else None,
            "sleep_target_min": sleep_target,
        },
    }
