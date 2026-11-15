"""Shared crew baseline calculation and readiness scoring services."""

import math
import sqlite3
from datetime import UTC, datetime
from typing import Any


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
            std_dev = round(max(abs(mean_val) * 0.04, 0.2), 4)

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
    """Compute readiness score, status label, and key vital summary for a crew member."""
    alerts = conn.execute(
        """
        SELECT severity
        FROM alerts
        WHERE crew_id = ? AND acknowledged_at_utc IS NULL
        """,
        (crew_id,),
    ).fetchall()
    critical_count = sum(1 for a in alerts if a["severity"] == "CRITICAL")
    warning_count = sum(1 for a in alerts if a["severity"] == "WARNING")

    hr = _latest_metric(conn, crew_id, "resting_hr_bpm")
    hrv = _latest_metric(conn, crew_id, "hrv_rmssd_ms")
    spo2 = _latest_metric(conn, crew_id, "spo2_pct")

    sleep_row = conn.execute(
        """
        SELECT total_sleep_min, sleep_score
        FROM sleep_sessions
        WHERE crew_id = ?
        ORDER BY sleep_start_utc DESC, id DESC
        LIMIT 1
        """,
        (crew_id,),
    ).fetchone()
    sleep_hours = round(float(sleep_row["total_sleep_min"]) / 60.0, 1) if sleep_row else None
    sleep_score = int(sleep_row["sleep_score"]) if sleep_row else 85

    score = 94
    score -= critical_count * 22
    score -= warning_count * 9
    if sleep_score < 85:
        score -= min(12, (85 - sleep_score) // 2)
    if hrv is not None and hrv < 52.0:
        score -= 5
    score = max(35, min(100, score))

    if critical_count > 0 or score < 60:
        status_label = "Critical"
    elif warning_count > 0 or score < 78:
        status_label = "Attention"
    elif score < 88:
        status_label = "Nominal"
    else:
        status_label = "Optimal"

    return {
        "status": status_label,
        "readiness_score": score,
        "unread_alerts": len(alerts),
        "vitals": {
            "resting_hr_bpm": hr,
            "hrv_rmssd_ms": hrv,
            "spo2_pct": spo2,
            "sleep_hours_24h": sleep_hours,
        },
    }
