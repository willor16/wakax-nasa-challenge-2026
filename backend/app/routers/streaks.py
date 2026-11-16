"""Crew Streaks: the public board (screen 03) and each crew member's own streak panel."""

import json
import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, status

from app.auth_utils import CurrentCrew, ensure_crew_access
from app.db import open_connection
from app.services import habits
from app.services.crew_names import display_title
from app.services.mission_clock import day_label, mission_day

router = APIRouter(prefix="/api/v1", tags=["streaks"])

WINDOW_DAYS = 7
PERSONAL_WINDOW_DAYS = 14
CONSISTENCY_DAYS = 30


def _streak_days(conn: sqlite3.Connection, crew_id: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        """SELECT streak_date_utc, daily_compliant, habits_done, habits_json
           FROM streak_days WHERE crew_id = ?""",
        (crew_id,),
    ).fetchall()
    return {r["streak_date_utc"]: r for r in rows}


def _day_entries(
    conn: sqlite3.Connection, by_day: dict[str, sqlite3.Row], window: list[date]
) -> list[dict]:
    """One entry per day of the window: logged, compliant, habits done and post-EVA shield."""
    entries = []
    for day in window:
        rec = by_day.get(day.isoformat())
        flags = json.loads(rec["habits_json"]) if rec else {}
        entries.append(
            {
                "date_utc": day.isoformat(),
                "day_label": day_label(mission_day(conn, day)),
                "logged": rec is not None,
                "compliant": bool(rec and rec["daily_compliant"]),
                "habits_done": int(rec["habits_done"]) if rec else 0,
                "shield": bool(flags.get("shield")),
            }
        )
    return entries


def _window(anchor: date, days: int) -> list[date]:
    return [anchor - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


@router.get("/crew-streaks")
def get_crew_streaks() -> dict:
    """Streaks, last seven days and today's four habits for each crew member, plus the team."""
    with open_connection() as conn:
        members = conn.execute(
            "SELECT id, code, full_name, role, title_en FROM crew_members "
            "WHERE is_active = 1 ORDER BY code ASC"
        ).fetchall()
        habits_day = habits.current_day(conn)
        anchor = date.fromisoformat(habits_day)
        window = _window(anchor, WINDOW_DAYS)

        crew: list[dict] = []
        day_sets: list[set[str]] = []
        todays: list[dict] = []
        for m in members:
            by_day = _streak_days(conn, m["id"])
            compliant = {d for d, r in by_day.items() if r["daily_compliant"]}
            day_sets.append(compliant)
            summary = habits.day_habits(conn, m["id"], habits_day)
            todays.append(summary)
            last_7 = _day_entries(conn, by_day, window)
            active = habits.active_streak(compliant, anchor)
            crew.append(
                {
                    "id": m["id"],
                    "code": m["code"],
                    "full_name": m["full_name"],
                    "title_en": display_title(m),
                    "active_streak_days": active,
                    "best_streak_days": max(habits.best_streak(compliant), active),
                    "today_compliant": anchor.isoformat() in compliant,
                    "today_shield": last_7[-1]["shield"],
                    "habits_done_today": summary["habits_done"],
                    "last_7_days": last_7,
                    "habits": [
                        {"key": key, "label": h["label"], "pct": h["pct"]}
                        for key, h in summary["habits"].items()
                    ],
                }
            )

        shared = set.intersection(*day_sets) if day_sets else set()
        team_streak = habits.active_streak(shared, anchor)
        count = len(crew)

        def average(key: str) -> int | None:
            return round(sum(t["habits"][key]["pct"] for t in todays) / count) if count else None

        def met(key: str) -> int:
            return sum(1 for t in todays if t["habits"][key]["pct"] >= 100)

        since = (anchor - timedelta(days=CONSISTENCY_DAYS - 1)).isoformat()
        totals = conn.execute(
            """SELECT SUM(habits_done) AS done, COUNT(*) AS days FROM streak_days
               WHERE streak_date_utc >= ? AND streak_date_utc <= ?""",
            (since, anchor.isoformat()),
        ).fetchone()
        consistency = round(totals["done"] / (totals["days"] * 4) * 100) if totals["days"] else None
        eva_rest = sum(1 for t in todays if t["after_eva"])
        completed = (
            round(sum(t["habits_done"] for t in todays) / (count * 4) * 100) if count else None
        )

        return {
            "habits_date_utc": habits_day,
            "today_label": day_label(mission_day(conn, anchor)),
            "window": [
                {"date_utc": d.isoformat(), "day_label": day_label(mission_day(conn, d))}
                for d in window
            ],
            "team_streak_days": team_streak,
            "team_completed_pct": completed,
            "team": {
                "hydration_pct": average("hydration"),
                "hydration_on_pace": met("hydration"),
                "nutrition_pct": average("nutrition"),
                "nutrition_met": met("nutrition"),
                "exercise_pct": average("exercise"),
                "exercise_met": met("exercise") - eva_rest,
                "post_eva_rest": eva_rest,
                "consistency_30d_pct": consistency,
                "active_streaks": sum(1 for c in crew if c["active_streak_days"] > 0),
                "crew_count": count,
            },
            "crew": crew,
        }


@router.get("/streaks/{crew_id}")
def get_personal_streak(crew_id: str, claims: CurrentCrew) -> dict:
    """One crew member's own streak: record, post-EVA shield, today's habits and 14 days."""
    ensure_crew_access(claims, crew_id)
    with open_connection() as conn:
        member = conn.execute(
            "SELECT id, code, full_name, role, title_en FROM crew_members WHERE id = ?",
            (crew_id,),
        ).fetchone()
        if member is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")
        habits_day = habits.current_day(conn)
        anchor = date.fromisoformat(habits_day)
        by_day = _streak_days(conn, crew_id)
        compliant = {d for d, r in by_day.items() if r["daily_compliant"]}
        summary = habits.day_habits(conn, crew_id, habits_day)
        history = _day_entries(conn, by_day, _window(anchor, PERSONAL_WINDOW_DAYS))
        active = habits.active_streak(compliant, anchor)
        logged = [d for d in history if d["logged"]]
        return {
            "crew": {"id": member["id"], "code": member["code"],
                     "full_name": member["full_name"], "title_en": display_title(member)},
            "habits_date_utc": habits_day,
            "today_label": day_label(mission_day(conn, anchor)),
            "active_streak_days": active,
            "best_streak_days": max(habits.best_streak(compliant), active),
            "shield_active": history[-1]["shield"],
            "after_eva_today": summary["after_eva"],
            "today_compliant": anchor.isoformat() in compliant,
            "habits_done_today": summary["habits_done"],
            "habits": [
                {"key": key, "label": h["label"], "value": h["value"], "target": h["target"],
                 "unit": h["unit"], "pct": h["pct"]}
                for key, h in summary["habits"].items()
            ],
            "last_14_days": history,
            "consistency_14d_pct": round(sum(d["habits_done"] for d in logged)
                                         / (len(history) * len(habits.HABIT_KEYS)) * 100),
            "rules": {"compliant_habits": habits.COMPLIANT_HABITS,
                      "shield_habits": habits.SHIELD_HABITS},
        }
