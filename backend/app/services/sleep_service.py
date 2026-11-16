"""Sleep sessions: capture and the Sleep Architecture & Quality view (screen 07).

A night is stored as one session plus its stage bouts. Stage bouts come from the
sleep band (the onboard sensor simulator stands in for it during demonstrations);
when only the sleep window is known, the session is kept without stage detail
and the screen says so instead of guessing an architecture.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import timedelta
from typing import Any

from app.services.clinical_view import crew_row
from app.services.contracts import update_streaks
from app.services.mission_clock import (
    current_stage,
    day_label,
    mission_day,
    parse_iso,
    to_iso,
    utc_now,
)
from app.services.reference_ranges import sleep_reference
from app.services.sensor_simulator import simulator_enabled
from app.services.sleep_metrics import build_night, score_label, sleep_score

STAGE_ORDER = ("DEEP", "REM", "LIGHT", "AWAKE")
STAGE_NAMES = {
    "DEEP": "Deep Sleep",
    "REM": "REM Sleep",
    "LIGHT": "Light Sleep",
    "AWAKE": "Awake Time",
}
PERIOD_NIGHTS = {"last_night": 1, "7d": 7, "14d": 14, "30d": 30}
MAX_WINDOW_MIN = 16 * 60
AWAKE_LIMIT_MIN = 35


def _hhmm(text: str) -> str:
    return text[11:16]


def create_sleep_session(
    conn: sqlite3.Connection,
    crew_id: str,
    sleep_start_utc: str,
    sleep_end_utc: str,
    stages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Store last night's sleep window (and its stage bouts when the band provided them)."""
    if crew_row(conn, crew_id) is None:
        raise LookupError("Crew member not found.")
    start, end = parse_iso(sleep_start_utc), parse_iso(sleep_end_utc)
    in_bed = int((end - start).total_seconds() // 60)
    if in_bed <= 0:
        raise ValueError("Wake time must be after sleep onset.")
    if in_bed > MAX_WINDOW_MIN:
        raise ValueError("A sleep window cannot be longer than 16 hours.")
    if end > utc_now() + timedelta(minutes=5):
        raise ValueError("Wake time cannot be in the future.")
    overlap = conn.execute(
        """SELECT 1 FROM sleep_sessions WHERE crew_id = ? AND sleep_start_utc < ?
           AND sleep_end_utc > ?""",
        (crew_id, to_iso(end), to_iso(start)),
    ).fetchone()
    if overlap:
        raise ValueError("A sleep window is already logged for that night.")

    bouts: list[tuple[str, int]] = []
    if stages:
        bouts = [(s["stage"], int(s["duration_min"])) for s in stages]
        if abs(sum(m for _, m in bouts) - in_bed) > 5:
            raise ValueError("The sleep stages do not add up to the sleep window.")
    elif simulator_enabled():
        rng = random.Random(f"{crew_id}{sleep_start_utc}")
        awake = min(in_bed // 8, rng.randint(14, 30))
        bouts = build_night(
            in_bed - awake,
            awake,
            rng.uniform(16, 23),
            rng.uniform(20, 25),
            [rng.uniform(-0.3, 0.3) for _ in range(7)],
        )
        drift = in_bed - sum(m for _, m in bouts)
        stage, minutes = bouts[-1]
        bouts[-1] = (stage, max(1, minutes + drift))

    minutes = {s: sum(m for st, m in bouts if st == s) for s in STAGE_ORDER}
    asleep = in_bed - minutes["AWAKE"]
    score = (
        sleep_score(asleep, in_bed, minutes["DEEP"], minutes["REM"], minutes["AWAKE"])
        if bouts
        else sleep_score(asleep, in_bed, asleep * 0.2, asleep * 0.22, 0)
    )
    cursor = conn.execute(
        """INSERT INTO sleep_sessions (crew_id, mission_stage, sleep_start_utc, sleep_end_utc,
           total_sleep_min, time_in_bed_min, sleep_score, sleep_efficiency_pct, deep_min, rem_min,
           light_min, awake_min, recorded_at_utc, stages_recorded)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            crew_id,
            current_stage(conn),
            to_iso(start),
            to_iso(end),
            asleep,
            in_bed,
            score,
            round(asleep / in_bed * 100, 1),
            minutes["DEEP"],
            minutes["REM"],
            minutes["LIGHT"],
            minutes["AWAKE"],
            to_iso(utc_now()),
            int(bool(bouts)),
        ),
    )
    session_id = int(cursor.lastrowid)
    cursor_at = start
    for stage, mins in bouts:
        conn.execute(
            "INSERT INTO sleep_stages (session_id, stage, start_utc, end_utc, duration_min) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                stage,
                to_iso(cursor_at),
                to_iso(cursor_at + timedelta(minutes=mins)),
                mins,
            ),
        )
        cursor_at += timedelta(minutes=mins)
    update_streaks(conn, crew_id, to_iso(end)[:10])
    return {
        "id": session_id,
        "total_sleep_min": asleep,
        "time_in_bed_min": in_bed,
        "sleep_score": score,
        "stages_recorded": bool(bouts),
    }


def _stage_cards(minutes: dict[str, float], asleep: float, in_bed: float) -> list[dict[str, Any]]:
    ref = sleep_reference()
    targets = {"DEEP": ref["deep_pct"], "REM": ref["rem_pct"], "LIGHT": ref["light_pct"]}
    good = {"DEEP": "Restorative", "REM": "Optimal", "LIGHT": "Balanced"}
    cards = []
    for stage in ("DEEP", "REM", "LIGHT"):
        low, high = targets[stage]
        pct = round(minutes[stage] / asleep * 100) if asleep else 0
        if low <= pct <= high:
            status, text = "NOMINAL", good[stage]
        else:
            status, text = "WATCH", "Below Target" if pct < low else "Above Target"
        cards.append(
            {
                "stage": stage,
                "label": STAGE_NAMES[stage],
                "minutes": round(minutes[stage]),
                "pct": pct,
                "target_low_pct": low,
                "target_high_pct": high,
                "status": status,
                "status_text": text,
            }
        )
    awake_pct = round(minutes["AWAKE"] / in_bed * 100) if in_bed else 0
    over = minutes["AWAKE"] > AWAKE_LIMIT_MIN
    cards.append(
        {
            "stage": "AWAKE",
            "label": STAGE_NAMES["AWAKE"],
            "minutes": round(minutes["AWAKE"]),
            "pct": awake_pct,
            "limit_min": AWAKE_LIMIT_MIN,
            "status": "WARNING" if over else "NOMINAL",
            "status_text": "Fragmented" if over else "Brief",
        }
    )
    return cards


def _night(conn: sqlite3.Connection, session: sqlite3.Row) -> dict[str, Any]:
    bouts = conn.execute(
        "SELECT stage, start_utc, end_utc, duration_min FROM sleep_stages WHERE session_id = ? "
        "ORDER BY start_utc ASC, id ASC",
        (session["id"],),
    ).fetchall()
    lapses = []
    for stage in STAGE_ORDER:
        own = [b for b in bouts if b["stage"] == stage]
        if not own:
            continue
        durations = [b["duration_min"] for b in own]
        lapses.append(
            {
                "stage": stage,
                "label": STAGE_NAMES[stage].replace(" Time", ""),
                "bouts": len(own),
                "avg_min": round(sum(durations) / len(durations)),
                "max_min": max(durations),
                "total_min": sum(durations),
                "intervals": [
                    {
                        "start": _hhmm(b["start_utc"]),
                        "end": _hhmm(b["end_utc"]),
                        "minutes": b["duration_min"],
                    }
                    for b in own
                ],
            }
        )
    return {
        "bouts": [
            {
                "stage": b["stage"],
                "start_utc": b["start_utc"],
                "end_utc": b["end_utc"],
                "minutes": b["duration_min"],
            }
            for b in bouts
        ],
        "bout_count": len(bouts),
        "cycles": sum(1 for b in bouts if b["stage"] == "REM"),
        "lapses": lapses,
    }


def build_sleep_monitor(
    conn: sqlite3.Connection, crew_id: str, period: str = "last_night"
) -> dict[str, Any] | None:
    if crew_row(conn, crew_id) is None:
        return None
    nights = PERIOD_NIGHTS[period]
    sessions = conn.execute(
        "SELECT * FROM sleep_sessions WHERE crew_id = ? "
        "ORDER BY sleep_end_utc DESC, id DESC LIMIT ?",
        (crew_id, nights),
    ).fetchall()
    ref = sleep_reference()
    target_min = ref["total_min"]["nominal"][0]
    base = {
        "crew_id": crew_id,
        "period": period,
        "nights_requested": nights,
        "target_min": target_min,
        "nights": len(sessions),
    }
    if not sessions:
        return {**base, "summary": None, "stages": [], "night": None, "trend": []}

    last = sessions[0]
    count = len(sessions)

    def avg(column: str) -> float:
        return sum(s[column] for s in sessions) / count

    asleep, in_bed = avg("total_sleep_min"), avg("time_in_bed_min")
    minutes = {
        "DEEP": avg("deep_min"),
        "REM": avg("rem_min"),
        "LIGHT": avg("light_min"),
        "AWAKE": avg("awake_min"),
    }
    score = round(avg("sleep_score"))
    staged = all(s["stages_recorded"] for s in sessions)
    trend = [
        {
            "date_utc": s["sleep_end_utc"][:10],
            "recorded_at_utc": s["sleep_end_utc"],
            "mission_stage": s["mission_stage"],
            "day_label": day_label(mission_day(conn, parse_iso(s["sleep_end_utc"]))),
            "total_min": s["total_sleep_min"],
            "score": s["sleep_score"],
            "deep_min": s["deep_min"],
            "rem_min": s["rem_min"],
            "light_min": s["light_min"],
            "awake_min": s["awake_min"],
        }
        for s in reversed(sessions)
    ]
    return {
        **base,
        "summary": {
            "score": score,
            "score_label": score_label(score, asleep),
            "total_min": round(asleep),
            "target_met": asleep >= target_min,
            "in_bed_min": round(in_bed),
            "efficiency_pct": round(asleep / in_bed * 100) if in_bed else None,
            "day_label": day_label(mission_day(conn, parse_iso(last["sleep_end_utc"]))),
            "window_start": _hhmm(last["sleep_start_utc"]),
            "window_end": _hhmm(last["sleep_end_utc"]),
            "window_start_utc": last["sleep_start_utc"],
            "window_end_utc": last["sleep_end_utc"],
            "stages_recorded": staged,
        },
        "stages": _stage_cards(minutes, asleep, in_bed) if staged else [],
        "night": _night(conn, last) if last["stages_recorded"] else None,
        "trend": trend,
    }
