"""Public read-only Crew Streaks endpoints (D1-06)."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from app.db import open_connection

router = APIRouter(prefix="/api/v1", tags=["streaks"])


def _compute_streak_metrics(day_map: dict[str, dict], window_dates: list[str]) -> dict:
    last_7 = []
    for day in window_dates:
        rec = day_map.get(day)
        last_7.append(
            {
                "date_utc": day,
                "compliant": bool(rec and int(rec["daily_compliant"]) == 1),
                "logs_completed": int(rec["logs_completed"]) if rec else 0,
                "habits_met": bool(rec and int(rec["habits_met"]) == 1),
            }
        )

    all_compliant_days = sorted(
        day for day, rec in day_map.items() if int(rec["daily_compliant"]) == 1
    )

    best_streak = 0
    current_run = 0
    prev_dt: datetime | None = None
    for day_str in all_compliant_days:
        dt = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=UTC)
        if prev_dt is not None and (dt - prev_dt).days == 1:
            current_run += 1
        else:
            current_run = 1
        best_streak = max(best_streak, current_run)
        prev_dt = dt

    active_streak = 0
    if all_compliant_days:
        cursor_dt = datetime.strptime(all_compliant_days[-1], "%Y-%m-%d").replace(tzinfo=UTC)
        compliant_set = set(all_compliant_days)
        while cursor_dt.strftime("%Y-%m-%d") in compliant_set:
            active_streak += 1
            cursor_dt -= timedelta(days=1)

    return {
        "active_streak_days": active_streak,
        "best_streak_days": best_streak,
        "last_7_days": last_7,
    }


@router.get("/crew-streaks")
def get_crew_streaks() -> dict:
    """Return read-only individual and team compliance streaks for the last 7 UTC days."""
    with open_connection() as conn:
        members = conn.execute(
            """
            SELECT id, code, full_name, role
            FROM crew_members
            WHERE is_active = 1
            ORDER BY code ASC
            """
        ).fetchall()

        latest_row = conn.execute(
            "SELECT MAX(streak_date_utc) AS latest_date FROM streak_days"
        ).fetchone()
        anchor_str = (
            latest_row["latest_date"]
            if latest_row and latest_row["latest_date"]
            else datetime.now(UTC).strftime("%Y-%m-%d")
        )
        anchor_dt = datetime.strptime(anchor_str, "%Y-%m-%d").replace(tzinfo=UTC)
        window_dates = [
            (anchor_dt - timedelta(days=offset)).strftime("%Y-%m-%d")
            for offset in range(6, -1, -1)
        ]

        crew_list: list[dict] = []
        compliant_days_per_member: list[set[str]] = []

        for m in members:
            rows = conn.execute(
                """
                SELECT streak_date_utc, logs_completed, habits_met, daily_compliant
                FROM streak_days
                WHERE crew_id = ?
                ORDER BY streak_date_utc ASC
                """,
                (m["id"],),
            ).fetchall()
            day_map = {r["streak_date_utc"]: dict(r) for r in rows}
            metrics = _compute_streak_metrics(day_map, window_dates)
            compliant_days_per_member.append(
                {day for day, rec in day_map.items() if int(rec["daily_compliant"]) == 1}
            )
            crew_list.append(
                {
                    "id": m["id"],
                    "code": m["code"],
                    "full_name": m["full_name"],
                    "role": m["role"],
                    **metrics,
                }
            )

        team_streak = 0
        if compliant_days_per_member:
            shared_days = sorted(set.intersection(*compliant_days_per_member))
            if shared_days:
                cursor_dt = datetime.strptime(shared_days[-1], "%Y-%m-%d").replace(tzinfo=UTC)
                shared_set = set(shared_days)
                while cursor_dt.strftime("%Y-%m-%d") in shared_set:
                    team_streak += 1
                    cursor_dt -= timedelta(days=1)

        total_slots = len(crew_list) * len(window_dates)
        compliant_slots = sum(
            1
            for member in crew_list
            for day_entry in member["last_7_days"]
            if day_entry["compliant"]
        )
        team_compliance_pct = round((compliant_slots / total_slots) * 100) if total_slots else 0

    return {
        "window_dates": window_dates,
        "team_streak_days": team_streak,
        "team_compliance_pct": team_compliance_pct,
        "eva_shield_ready": team_compliance_pct >= 80,
        "crew": crew_list,
    }
