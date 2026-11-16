"""Cabin environment: latest snapshot, ingestion and health advisories.

Limits come from the reference ranges (comfort zone 20-25 C and 30-60% RH, quiet
cabin under 55 dBA for heart and lung recordings, CO2 target and alert levels,
daily radiation dose against the yearly working limit).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from typing import Any

from app.services import reference_ranges
from app.services.alert_engine import care_steps
from app.services.alert_rules import QuietHours, Severity, format_amount, should_defer
from app.services.mission_clock import (
    PERIOD_HOURS,
    mission_elapsed_days,
    parse_iso,
    to_iso,
    utc_now,
)

MMHG_PER_ATM = 760.0
# Column in ``environment_readings`` -> reference metric.
CABIN_METRICS = {
    "co2_ppm": "cabin_co2_ppm",
    "temp_c": "cabin_temp_c",
    "humidity_pct": "cabin_humidity_pct",
    "noise_dba": "cabin_noise_dba",
    "radiation_msv": "radiation_daily_msv",
}
_ORDER = {"NOMINAL": 0, "WATCH": 1, "WARNING": 2, "CRITICAL": 3}
_GROUPS = {"radiation_daily_msv": ("radiation", "wiki-radiation-01")}
REPEAT = timedelta(hours=6)


def ppm_to_mmhg(ppm: float) -> float:
    """Partial pressure of CO2 at one atmosphere of cabin pressure."""
    return round(ppm * MMHG_PER_ATM / 1_000_000.0, 2)


def mmhg_to_ppm(mmhg: float) -> float:
    return mmhg / MMHG_PER_ATM * 1_000_000.0


def co2_limits_mmhg() -> dict[str, float]:
    entry = reference_ranges.metric("cabin_co2_ppm") or {}
    return {
        "target": ppm_to_mmhg(entry.get("nominal_max", 0)),
        "alert": ppm_to_mmhg(entry.get("warning_max", 0)),
        "physician": ppm_to_mmhg(entry.get("critical_threshold", 0)),
    }


def cabin_snapshot(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Latest cabin reading with a status per value, or None before the first reading."""
    row = conn.execute(
        "SELECT * FROM environment_readings ORDER BY recorded_at_utc DESC, id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    statuses = {
        col: reference_ranges.status_label(key, row[col]) for col, key in CABIN_METRICS.items()
    }
    worst = max(statuses.values(), key=_ORDER.__getitem__)
    days = mission_elapsed_days(conn) or 0
    total = conn.execute(
        """SELECT SUM(daily) FROM (SELECT AVG(radiation_msv) AS daily FROM environment_readings
           GROUP BY substr(recorded_at_utc, 1, 10))"""
    ).fetchone()[0]
    radiation = reference_ranges.radiation_reference()
    comfort_t = reference_ranges.metric("cabin_temp_c") or {}
    comfort_h = reference_ranges.metric("cabin_humidity_pct") or {}
    noise = reference_ranges.metric("cabin_noise_dba") or {}
    return {
        "location_en": row["location_en"],
        "recorded_at_utc": row["recorded_at_utc"],
        "temp_c": row["temp_c"],
        "humidity_pct": row["humidity_pct"],
        "noise_dba": row["noise_dba"],
        "co2_ppm": row["co2_ppm"],
        "co2_mmhg": ppm_to_mmhg(row["co2_ppm"]),
        "radiation_msv_day": row["radiation_msv"],
        "radiation_mission_msv": round(total or 0.0, 1),
        "radiation_yearly_limit_msv": radiation["occupational_msv_year"],
        "mission_days": days,
        "kp_index": row["kp_index"],
        "solar_event": bool(row["solar_event_flag"]),
        "status": worst,
        "statuses": statuses,
        "limits": {
            "temp_c": [comfort_t.get("nominal_min"), comfort_t.get("nominal_max")],
            "humidity_pct": [comfort_h.get("nominal_min"), comfort_h.get("nominal_max")],
            "noise_dba_max": noise.get("nominal_max"),
            "co2_mmhg": co2_limits_mmhg(),
            "radiation_msv_day_max": (reference_ranges.metric("radiation_daily_msv") or {}).get(
                "nominal_max"
            ),
        },
    }


def co2_trend(conn: sqlite3.Connection, period: str = "24h") -> list[dict[str, Any]]:
    """Cabin CO2 in mmHg, oldest first: every reading for 24 h, hourly averages beyond that
    (a 30-day window stays under 720 points)."""
    latest = conn.execute("SELECT MAX(recorded_at_utc) FROM environment_readings").fetchone()[0]
    if latest is None:
        return []
    hours = PERIOD_HOURS[period] or 24 * 365
    since = to_iso(parse_iso(latest) - timedelta(hours=hours))
    if hours <= 24:
        rows = conn.execute(
            "SELECT recorded_at_utc, co2_ppm FROM environment_readings "
            "WHERE recorded_at_utc >= ? ORDER BY recorded_at_utc ASC",
            (since,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT substr(recorded_at_utc, 1, 13) || ':00:00Z' AS recorded_at_utc,
                      AVG(co2_ppm) AS co2_ppm
               FROM environment_readings WHERE recorded_at_utc >= ?
               GROUP BY substr(recorded_at_utc, 1, 13) ORDER BY 1 ASC""",
            (since,),
        ).fetchall()
    return [
        {"recorded_at_utc": r["recorded_at_utc"], "co2_mmhg": ppm_to_mmhg(r["co2_ppm"])}
        for r in rows
    ]



def _cabin_alert(
    conn: sqlite3.Connection,
    metric_key: str,
    value: float,
    severity: Severity,
    recorded_at_utc: str,
) -> list[int]:
    """One advisory per active crew member; the cabin affects everyone."""
    entry = reference_ranges.metric(metric_key) or {}
    name, unit = entry.get("display_name_en", "Cabin"), entry.get("unit", "")
    above = value > entry.get("nominal_max", value)
    shown, shown_unit = (
        (ppm_to_mmhg(value), "mmHg") if metric_key == "cabin_co2_ppm" else (value, unit)
    )
    word = {Severity.INFO: "slightly ", Severity.WARNING: "", Severity.CRITICAL: "dangerously "}
    title = (
        f"{name} {word[severity]}{'high' if above else 'low'} ({format_amount(shown, shown_unit)})"
    )
    since = to_iso(parse_iso(recorded_at_utc) - REPEAT)
    group, article = _GROUPS.get(metric_key, ("cabin_air", "wiki-co2-01"))
    article_ok = conn.execute("SELECT 1 FROM wiki_articles WHERE id = ?", (article,)).fetchone()
    quiet = conn.execute(
        "SELECT quiet_hours_start_utc AS s, quiet_hours_end_utc AS e FROM mission WHERE id = 1"
    ).fetchone()
    window = QuietHours(quiet["s"], quiet["e"]) if quiet else QuietHours()
    deferred = should_defer(severity, parse_iso(recorded_at_utc), window)
    message = (
        "Affects the whole crew. Follow the care steps now and call the crew physician."
        if severity is Severity.CRITICAL
        else "Affects the whole crew. Review preventive care on the right."
    )
    created: list[int] = []
    for crew in conn.execute("SELECT id FROM crew_members WHERE is_active = 1").fetchall():
        repeat = conn.execute(
            """SELECT severity FROM alerts WHERE crew_id = ? AND category = 'ENVIRONMENT'
               AND title_en LIKE ? AND created_at_utc >= ?""",
            (crew["id"], f"{name}%", since),
        ).fetchall()
        if any(Severity[r["severity"]] >= severity for r in repeat):
            continue
        cursor = conn.execute(
            """INSERT INTO alerts (crew_id, measurement_id, severity, category, title_en,
               message_en, recommended_actions_json, wiki_article_id, is_quiet_deferred,
               created_at_utc) VALUES (?, NULL, ?, 'ENVIRONMENT', ?, ?, ?, ?, ?, ?)""",
            (
                crew["id"],
                severity.name,
                title,
                message,
                json.dumps(care_steps(group, severity)),
                article if article_ok else None,
                int(deferred),
                recorded_at_utc,
            ),
        )
        created.append(int(cursor.lastrowid))
    return created


def record_reading(conn: sqlite3.Connection, reading: dict[str, Any]) -> dict[str, Any]:
    """Store a cabin reading and raise advisories for values outside the reference limits."""
    recorded = reading.get("recorded_at_utc") or to_iso(utc_now())
    conn.execute(
        """INSERT INTO environment_readings (co2_ppm, noise_dba, temp_c, humidity_pct,
           radiation_msv, solar_event_flag, recorded_at_utc, kp_index, location_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            reading["co2_ppm"],
            reading["noise_dba"],
            reading["temp_c"],
            reading["humidity_pct"],
            reading.get("radiation_msv", 0.0),
            int(bool(reading.get("solar_event"))),
            recorded,
            reading.get("kp_index"),
            reading.get("location_en") or "Habitat A",
        ),
    )
    alerts: list[int] = []
    for column, metric_key in CABIN_METRICS.items():
        value = reading.get(column)
        severity = reference_ranges.classify(metric_key, value)
        if severity is not None:
            alerts.extend(_cabin_alert(conn, metric_key, float(value), severity, recorded))
    return {"recorded_at_utc": recorded, "alerts_created": alerts}


# Cabin alert mode (the whole cockpit turns red) is reserved for emergencies that need
# everyone's attention now: a life-threatening vital sign or a dangerous cabin reading.
EMERGENCY_CATEGORIES = ("VITALS", "RESPIRATORY", "ENVIRONMENT")


def cabin_mode(conn: sqlite3.Connection) -> str:
    marks = ",".join("?" for _ in EMERGENCY_CATEGORIES)
    urgent = conn.execute(
        f"""SELECT COUNT(*) FROM alerts WHERE acknowledged_at_utc IS NULL
            AND severity = 'CRITICAL' AND category IN ({marks})""",
        EMERGENCY_CATEGORIES,
    ).fetchone()[0]
    return "critical" if urgent else "nominal"
