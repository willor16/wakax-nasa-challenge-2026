"""Read helpers shared by the results screens.

Every screen shows a reading the same way: the latest stored value, its status
from the single reference catalog (plus personal drift and loss against the
pre-flight value) and the personal baseline. Nothing is filled in when a
reading is missing - the view simply says there is no data yet.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.services import reference_ranges
from app.services.alert_rules import (
    MIN_BASELINE_SAMPLES,
    Baseline,
    Severity,
    classify_z,
    z_score,
)
from app.services.mission_clock import day_label, mission_day, parse_iso

STAGES = ("LAUNCH", "MISSION", "RETURN")
_STATUS = {
    None: "NOMINAL",
    Severity.INFO: "WATCH",
    Severity.WARNING: "WARNING",
    Severity.CRITICAL: "CRITICAL",
}


def latest(
    conn: sqlite3.Connection, crew_id: str, metric_key: str, stage: str | None = None
) -> sqlite3.Row | None:
    """Most recent stored reading of a metric (optionally within one mission stage)."""
    sql = """SELECT id, value_num, payload_json, recorded_at_utc, mission_stage, source_type
             FROM measurements WHERE crew_id = ? AND metric_key = ? AND value_num IS NOT NULL"""
    params: list[Any] = [crew_id, metric_key]
    if stage:
        sql += " AND mission_stage = ?"
        params.append(stage)
    return conn.execute(sql + " ORDER BY recorded_at_utc DESC, id DESC LIMIT 1", params).fetchone()


def baseline(conn: sqlite3.Connection, crew_id: str, metric_key: str) -> Baseline | None:
    row = conn.execute(
        "SELECT mean_val, std_dev, sample_count FROM baselines "
        "WHERE crew_id = ? AND metric_key = ?",
        (crew_id, metric_key),
    ).fetchone()
    return Baseline(row["mean_val"], row["std_dev"], row["sample_count"]) if row else None


def stage_averages(
    conn: sqlite3.Connection, crew_id: str, metric_key: str
) -> dict[str, float | None]:
    """Average per mission stage, for the Launch / Mission / Return comparison."""
    rows = conn.execute(
        """SELECT mission_stage, AVG(value_num) AS avg FROM measurements
           WHERE crew_id = ? AND metric_key = ? AND value_num IS NOT NULL GROUP BY mission_stage""",
        (crew_id, metric_key),
    ).fetchall()
    found = {r["mission_stage"]: r["avg"] for r in rows}
    return {stage: (round(found[stage], 2) if stage in found else None) for stage in STAGES}


def crew_sex(conn: sqlite3.Connection, crew_id: str) -> str | None:
    """``"F"`` / ``"M"`` for the crew member (None when not recorded)."""
    row = conn.execute("SELECT sex FROM crew_members WHERE id = ?", (crew_id,)).fetchone()
    return row["sex"] if row else None


def assess(
    metric_key: str, value: float | None, base: Baseline | None, sex: str | None = None
) -> tuple[str, bool]:
    """``(status, is_above)`` using the same rules (and sex-specific limits) as the alert engine."""
    if value is None:
        return "NO_DATA", False
    entry = reference_ranges.metric(metric_key) or {}
    limits = reference_ranges.limits_for_sex(metric_key, sex) or entry
    fixed = reference_ranges.classify(metric_key, value, sex)
    direction = entry.get("drift", "none")
    z = None if direction == "none" else z_score(value, base, entry.get("drift_sd_floor", 0.0))
    if z is not None and ((direction == "up" and z < 0) or (direction == "down" and z > 0)):
        z = None
    drift = classify_z(z)
    if fixed is None and drift is not None:
        drift = Severity.INFO
    relative = reference_ranges.classify_relative(
        metric_key, value, base.mean_val if base else None
    )
    found = [s for s in (fixed, drift, relative) if s is not None]
    severity = max(found) if found else None
    if fixed is not None:
        above = value > (limits.get("nominal_max") or value)
    elif relative is not None and (drift is None or relative >= drift):
        above = False
    else:
        above = bool(z and z > 0)
    return _STATUS[severity], above


def status_text(status: str, above: bool, nominal: str = "Optimal") -> str:
    """Short pill text for a status."""
    if status == "NO_DATA":
        return "No Data"
    if status == "NOMINAL":
        return nominal
    side = "High" if above else "Low"
    return {
        "WATCH": f"Slightly {side}",
        "WARNING": "Elevated" if above else "Low",
        "CRITICAL": f"Critical {side}",
    }[status]


def metric_view(
    conn: sqlite3.Connection,
    crew_id: str,
    metric_key: str,
    nominal_text: str = "Optimal",
    with_stages: bool = False,
) -> dict[str, Any]:
    """Everything a results row needs for one metric (limits calibrated to the crew's sex)."""
    entry = reference_ranges.metric(metric_key) or {}
    sex = crew_sex(conn, crew_id) if entry.get("by_sex") else None
    limits = reference_ranges.limits_for_sex(metric_key, sex) or entry
    row = latest(conn, crew_id, metric_key)
    base = baseline(conn, crew_id, metric_key)
    value = float(row["value_num"]) if row else None
    status, above = assess(metric_key, value, base, sex)
    usable = base is not None and base.sample_count >= MIN_BASELINE_SAMPLES
    spread = max(base.std_dev, entry.get("drift_sd_floor", 0.0)) if base else 0.0
    view: dict[str, Any] = {
        "metric_key": metric_key,
        "label": entry.get("display_name_en", metric_key),
        "unit": entry.get("unit", ""),
        "value": value,
        "recorded_at_utc": row["recorded_at_utc"] if row else None,
        "day_label": day_label(mission_day(conn, parse_iso(row["recorded_at_utc"])))
        if row
        else None,
        "status": status,
        "status_text": status_text(status, above, nominal_text),
        "is_above": above,
        "baseline_mean": round(base.mean_val, 3) if base else None,
        "baseline_low": round(base.mean_val - 2 * spread, 3) if usable else None,
        "baseline_high": round(base.mean_val + 2 * spread, 3) if usable else None,
        "baseline_pct": round(value / base.mean_val * 100, 1)
        if (value is not None and base and base.mean_val)
        else None,
        "nominal_min": limits.get("nominal_min"),
        "nominal_max": limits.get("nominal_max"),
        "scale_min": entry.get("plausible_min"),
        "scale_max": entry.get("plausible_max"),
    }
    if with_stages:
        view["stages"] = stage_averages(conn, crew_id, metric_key)
    return view


def payload(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    try:
        return json.loads(row["payload_json"] or "{}")
    except json.JSONDecodeError:
        return {}


def day_total(conn: sqlite3.Connection, crew_id: str, metric_key: str, day: str) -> float | None:
    row = conn.execute(
        """SELECT SUM(value_num) AS total FROM measurements WHERE crew_id = ? AND metric_key = ?
           AND substr(recorded_at_utc, 1, 10) = ?""",
        (crew_id, metric_key, day),
    ).fetchone()
    return float(row["total"]) if row and row["total"] is not None else None


def crew_row(conn: sqlite3.Connection, crew_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT id, code, full_name, role, title_en, age, sex, blood_type, height_cm
           FROM crew_members WHERE id = ? AND is_active = 1""",
        (crew_id,),
    ).fetchone()
