"""Daily habits and consistency streaks computed from the logged health data.

Four habits per day, each judged against the crew member's personal target:
hydration, nutrition, exercise (or post-spacewalk rest on exterior-work days)
and sleep routine (the night that ended that morning). A day counts for the
streak when at least three of the four habits are met. On exterior-work (EVA)
days the "EVA rest shield" protects the streak with two habits met, because
recovery replaces part of the routine.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from app.services.mission_clock import to_iso, utc_now
from app.services.reference_ranges import personal_targets

HABIT_KEYS = ("hydration", "nutrition", "exercise", "sleep")
COMPLIANT_HABITS = 3
SHIELD_HABITS = 2


def _day_sum(conn: sqlite3.Connection, crew_id: str, metric_key: str, day: str) -> float | None:
    row = conn.execute(
        """
        SELECT SUM(value_num) AS total FROM measurements
        WHERE crew_id = ? AND metric_key = ? AND substr(recorded_at_utc, 1, 10) = ?
        """,
        (crew_id, metric_key, day),
    ).fetchone()
    return float(row["total"]) if row and row["total"] is not None else None


def _latest_weight(conn: sqlite3.Connection, crew_id: str, day: str) -> float | None:
    row = conn.execute(
        """
        SELECT value_num FROM measurements
        WHERE crew_id = ? AND metric_key = 'body_weight_kg' AND substr(recorded_at_utc, 1, 10) <= ?
        ORDER BY recorded_at_utc DESC, id DESC LIMIT 1
        """,
        (crew_id, day),
    ).fetchone()
    return float(row["value_num"]) if row else None


def _sleep_minutes(conn: sqlite3.Connection, crew_id: str, day: str) -> float | None:
    row = conn.execute(
        """
        SELECT total_sleep_min FROM sleep_sessions
        WHERE crew_id = ? AND substr(sleep_end_utc, 1, 10) = ?
        ORDER BY sleep_end_utc DESC, id DESC LIMIT 1
        """,
        (crew_id, day),
    ).fetchone()
    return float(row["total_sleep_min"]) if row else None


def _pct(value: float | None, target: float) -> int:
    if value is None or target <= 0:
        return 0
    return int(min(100, round(value / target * 100)))


def day_habits(conn: sqlite3.Connection, crew_id: str, day: str) -> dict[str, Any]:
    """Progress of each habit on one UTC date (``YYYY-MM-DD``)."""
    crew = conn.execute(
        "SELECT sex, age, height_cm FROM crew_members WHERE id = ?", (crew_id,)
    ).fetchone()
    targets = personal_targets(dict(crew) if crew else {}, _latest_weight(conn, crew_id, day))
    hydration = _day_sum(conn, crew_id, "hydration_ml", day)
    calories = _day_sum(conn, crew_id, "calories_kcal", day)
    exercise = _day_sum(conn, crew_id, "exercise_min", day)
    eva = _day_sum(conn, crew_id, "eva_shift_min", day) or 0.0
    sleep = _sleep_minutes(conn, crew_id, day)

    after_eva = eva > 0
    habits = {
        "hydration": {"label": "Hydration", "value": hydration, "target": targets.hydration_ml,
                      "unit": "mL", "pct": _pct(hydration, targets.hydration_ml)},
        "nutrition": {"label": "Nutrition", "value": calories, "target": targets.calories_kcal,
                      "unit": "kcal", "pct": _pct(calories, targets.calories_kcal * 0.9)},
        "exercise": (
            {"label": "Post-EVA Rest", "value": eva, "target": eva, "unit": "min", "pct": 100}
            if after_eva else
            {"label": "Exercise", "value": exercise, "target": targets.exercise_min,
             "unit": "min", "pct": _pct(exercise, targets.exercise_min)}
        ),
        "sleep": {"label": "Sleep Routine", "value": sleep, "target": targets.sleep_min,
                  "unit": "min", "pct": _pct(sleep, targets.sleep_min)},
    }
    done = sum(1 for h in habits.values() if h["pct"] >= 100)
    logged = sum(1 for v in (hydration, calories, exercise if not after_eva else eva, sleep)
                 if v is not None)
    return {"date_utc": day, "habits": habits, "habits_done": done, "logs_completed": logged,
            "after_eva": after_eva}


def recompute_day(conn: sqlite3.Connection, crew_id: str, day: str) -> dict[str, Any]:
    """Store the habit summary of one day in ``streak_days`` and return it."""
    summary = day_habits(conn, crew_id, day)
    done = summary["habits_done"]
    shielded = summary["after_eva"] and SHIELD_HABITS <= done < COMPLIANT_HABITS
    compliant = int(done >= COMPLIANT_HABITS or shielded)
    habits_json = json.dumps({**{k: v["pct"] for k, v in summary["habits"].items()},
                              "after_eva": summary["after_eva"], "shield": shielded})
    conn.execute(
        """
        INSERT INTO streak_days (
            crew_id, streak_date_utc, logs_completed, habits_met, daily_compliant,
            updated_at_utc, habits_done, habits_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(crew_id, streak_date_utc) DO UPDATE SET
            logs_completed = excluded.logs_completed,
            habits_met = excluded.habits_met,
            daily_compliant = excluded.daily_compliant,
            updated_at_utc = excluded.updated_at_utc,
            habits_done = excluded.habits_done,
            habits_json = excluded.habits_json
        """,
        (crew_id, day, summary["logs_completed"], int(done == len(HABIT_KEYS)), compliant,
         to_iso(utc_now()), done, habits_json),
    )
    return {**summary, "daily_compliant": bool(compliant), "shield": shielded}


def compliant_days(conn: sqlite3.Connection, crew_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT streak_date_utc FROM streak_days WHERE crew_id = ? AND daily_compliant = 1",
        (crew_id,),
    ).fetchall()
    return {r["streak_date_utc"] for r in rows}


def _run_ending(days: set[str], end: date) -> int:
    count = 0
    cursor = end
    while cursor.isoformat() in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def active_streak(days: set[str], today: date) -> int:
    """Consecutive compliant days up to today; today still counts while in progress."""
    if today.isoformat() in days:
        return _run_ending(days, today)
    return _run_ending(days, today - timedelta(days=1))


def best_streak(days: set[str]) -> int:
    best = 0
    for text in days:
        start = datetime.strptime(text, "%Y-%m-%d").date()
        if (start - timedelta(days=1)).isoformat() in days:
            continue
        run, cursor = 0, start
        while cursor.isoformat() in days:
            run += 1
            cursor += timedelta(days=1)
        best = max(best, run)
    return best


def current_day(conn: sqlite3.Connection) -> str:
    """Date the habit panels describe: today once anything was logged, else the last logged day."""
    today = utc_now().date().isoformat()
    row = conn.execute(
        "SELECT MAX(streak_date_utc) FROM streak_days WHERE logs_completed > 0"
    ).fetchone()
    latest = row[0] if row and row[0] else today
    return today if latest >= today else latest
