import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from app.schemas.sleep import (
    HudTagTone,
    SleepAxisTickOut,
    SleepMonitorOut,
    SleepPeriod,
    SleepRibbonBoutOut,
    SleepRibbonLegendItemOut,
    SleepSessionCreatedOut,
    SleepSessionCreateIn,
    SleepStageCardOut,
    SleepStageLapseRowOut,
    SleepStageType,
)
from app.services.contracts import update_streaks

STAGE_LANE_MAP: dict[SleepStageType, int] = {
    "DEEP": 1,
    "LIGHT": 2,
    "REM": 3,
    "AWAKE": 4,
}

PERIOD_DAYS_MAP: dict[SleepPeriod, int] = {
    "last_night": 1,
    "7d": 7,
    "14d": 14,
    "30d": 30,
}


def _parse_iso_utc(raw: str) -> datetime:
    cleaned = raw.strip()
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _fmt_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_hm(mins: int | float) -> str:
    rounded = max(0, int(round(mins)))
    return f"{rounded // 60}h {rounded % 60:02d}m"


def _fmt_short_min(mins: int | float) -> str:
    rounded = max(0, int(round(mins)))
    if rounded < 60:
        return f"{rounded}m"
    return f"{rounded // 60}h {rounded % 60:02d}m"


def _compute_sleep_score(
    total_sleep_min: int,
    efficiency_pct: float,
    deep_min: int,
    rem_min: int,
) -> int:
    if total_sleep_min <= 0:
        return 0
    duration_pts = min(40.0, (total_sleep_min / 435.0) * 40.0)
    eff_pts = min(25.0, max(0.0, ((efficiency_pct - 65.0) / 30.0) * 25.0))
    deep_share = deep_min / total_sleep_min
    rem_share = rem_min / total_sleep_min
    deep_pts = min(18.0, (deep_share / 0.21) * 18.0)
    rem_pts = min(17.0, (rem_share / 0.23) * 17.0)
    return max(0, min(100, int(round(duration_pts + eff_pts + deep_pts + rem_pts))))


def _build_ultradian_bouts(
    start_dt: datetime,
    deep_min: int,
    rem_min: int,
    light_min: int,
    awake_min: int,
) -> list[tuple[SleepStageType, datetime, datetime, int]]:
    aw1 = max(2, round(awake_min * 0.34))
    aw2 = max(2, round(awake_min * 0.41))
    aw3 = max(0, awake_min - aw1 - aw2)

    d1 = max(8, round(deep_min * 0.45))
    d2 = max(6, round(deep_min * 0.34))
    d3 = max(0, deep_min - d1 - d2)

    r1 = max(6, round(rem_min * 0.18))
    r2 = max(8, round(rem_min * 0.26))
    r3 = max(8, round(rem_min * 0.32))
    r4 = max(0, rem_min - r1 - r2 - r3)

    light_weights = [0.12, 0.09, 0.15, 0.13, 0.18, 0.18, 0.15]
    light_parts = [max(4, round(light_min * w)) for w in light_weights[:-1]]
    light_parts.append(max(4, light_min - sum(light_parts)))

    plan: list[tuple[SleepStageType, int]] = [
        ("AWAKE", aw1),
        ("LIGHT", light_parts[0]),
        ("DEEP", d1),
        ("LIGHT", light_parts[1]),
        ("REM", r1),
        ("LIGHT", light_parts[2]),
        ("DEEP", d2),
        ("AWAKE", aw2),
        ("LIGHT", light_parts[3]),
        ("REM", r2),
        ("LIGHT", light_parts[4]),
        ("DEEP", d3),
        ("REM", r3),
        ("LIGHT", light_parts[5]),
        ("AWAKE", aw3),
        ("REM", r4),
        ("LIGHT", light_parts[6]),
    ]

    bouts: list[tuple[SleepStageType, datetime, datetime, int]] = []
    cursor = start_dt
    for stage_name, mins in plan:
        if mins <= 0:
            continue
        end_cursor = cursor + timedelta(minutes=mins)
        bouts.append((stage_name, cursor, end_cursor, mins))
        cursor = end_cursor
    return bouts


def _sync_latest_psych_sleep_window(conn: sqlite3.Connection, crew_id: str) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(psych_tests)").fetchall()}
    if not {"sleep_onset_utc", "wake_utc"}.issubset(cols):
        return

    psych_row = conn.execute(
        """
        SELECT mission_stage, sleep_onset_utc, wake_utc, recorded_at_utc
        FROM psych_tests
        WHERE crew_id = ? AND sleep_onset_utc IS NOT NULL AND wake_utc IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
        """,
        (crew_id,),
    ).fetchone()
    if psych_row is None:
        return

    latest_sleep = conn.execute(
        "SELECT recorded_at_utc FROM sleep_sessions WHERE crew_id = ? ORDER BY id DESC LIMIT 1",
        (crew_id,),
    ).fetchone()
    psych_rec = str(psych_row["recorded_at_utc"])
    if latest_sleep and str(latest_sleep["recorded_at_utc"]) >= psych_rec:
        return

    rec_dt = _parse_iso_utc(psych_rec)
    onset_parts = [int(x) for x in str(psych_row["sleep_onset_utc"]).split(":")]
    wake_parts = [int(x) for x in str(psych_row["wake_utc"]).split(":")]

    wake_dt = rec_dt.replace(hour=wake_parts[0], minute=wake_parts[1], second=0, microsecond=0)
    if wake_dt > rec_dt:
        wake_dt -= timedelta(days=1)
    onset_dt = wake_dt.replace(hour=onset_parts[0], minute=onset_parts[1])
    if onset_dt >= wake_dt:
        onset_dt -= timedelta(days=1)

    bed_min = max(60, int(round((wake_dt - onset_dt).total_seconds() / 60.0)))
    awake_min = max(12, round(bed_min * 0.055))
    sleep_min = max(45, bed_min - awake_min)
    deep_min = round(sleep_min * 0.215)
    rem_min = round(sleep_min * 0.245)
    light_min = max(15, sleep_min - deep_min - rem_min)
    eff_pct = round((sleep_min / bed_min) * 100.0, 1)
    score = _compute_sleep_score(sleep_min, eff_pct, deep_min, rem_min)

    cur = conn.execute(
        """
        INSERT INTO sleep_sessions (
            crew_id, mission_stage, sleep_start_utc, sleep_end_utc,
            total_sleep_min, time_in_bed_min, sleep_score, sleep_efficiency_pct,
            deep_min, rem_min, light_min, awake_min, recorded_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            crew_id,
            str(psych_row["mission_stage"]),
            _fmt_iso(onset_dt),
            _fmt_iso(wake_dt),
            sleep_min,
            bed_min,
            score,
            eff_pct,
            deep_min,
            rem_min,
            light_min,
            awake_min,
            psych_rec,
        ),
    )
    session_id = int(cur.lastrowid)
    bouts = _build_ultradian_bouts(onset_dt, deep_min, rem_min, light_min, awake_min)
    conn.executemany(
        """
        INSERT INTO sleep_stages (session_id, stage, start_utc, end_utc, duration_min)
        VALUES (?, ?, ?, ?, ?)
        """,
        [(session_id, st, _fmt_iso(s_dt), _fmt_iso(e_dt), dur) for st, s_dt, e_dt, dur in bouts],
    )
    conn.commit()


def ensure_sleep_history(conn: sqlite3.Connection, crew_id: str) -> None:
    _sync_latest_psych_sleep_window(conn, crew_id)

    rows = conn.execute(
        """
        SELECT id, mission_stage, sleep_start_utc, sleep_end_utc
        FROM sleep_sessions
        WHERE crew_id = ?
        ORDER BY sleep_start_utc DESC
        """,
        (crew_id,),
    ).fetchall()
    if len(rows) == 0 or len(rows) >= 15:
        return

    anchor_start = _parse_iso_utc(str(rows[-1]["sleep_start_utc"]))
    crew_seed_bias = sum(ord(ch) for ch in crew_id) % 7
    missing_nights = 30 - len(rows)

    for day_idx in range(1, missing_nights + 1):
        wave = ((day_idx + crew_seed_bias) % 5) - 2
        onset_shift = wave * 6
        night_start = (anchor_start - timedelta(days=day_idx)) + timedelta(minutes=onset_shift)

        total_sleep = 426 + wave * 9 + ((day_idx % 3) - 1) * 6
        awake_m = 24 + ((day_idx + crew_seed_bias) % 4) * 4
        in_bed = total_sleep + awake_m
        night_end = night_start + timedelta(minutes=in_bed)

        deep_m = round(total_sleep * (0.215 + (wave * 0.006)))
        rem_m = round(total_sleep * (0.242 - (wave * 0.004)))
        light_m = max(120, total_sleep - deep_m - rem_m)
        eff = round((total_sleep / in_bed) * 100.0, 1)
        score = _compute_sleep_score(total_sleep, eff, deep_m, rem_m)
        stage_label = "LAUNCH" if day_idx > 24 else "MISSION"

        cur = conn.execute(
            """
            INSERT INTO sleep_sessions (
                crew_id, mission_stage, sleep_start_utc, sleep_end_utc,
                total_sleep_min, time_in_bed_min, sleep_score, sleep_efficiency_pct,
                deep_min, rem_min, light_min, awake_min, recorded_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                crew_id,
                stage_label,
                _fmt_iso(night_start),
                _fmt_iso(night_end),
                total_sleep,
                in_bed,
                score,
                eff,
                deep_m,
                rem_m,
                light_m,
                awake_m,
                _fmt_iso(night_end),
            ),
        )
        sid = int(cur.lastrowid)
        bouts = _build_ultradian_bouts(night_start, deep_m, rem_m, light_m, awake_m)
        conn.executemany(
            """
            INSERT INTO sleep_stages (session_id, stage, start_utc, end_utc, duration_min)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(sid, st, _fmt_iso(s_dt), _fmt_iso(e_dt), dur) for st, s_dt, e_dt, dur in bouts],
        )

    conn.commit()


def create_sleep_session(
    conn: sqlite3.Connection, payload: SleepSessionCreateIn
) -> SleepSessionCreatedOut | None:
    crew_id = payload.crew_id.strip()
    crew_row = conn.execute(
        "SELECT id FROM crew_members WHERE id = ? AND is_active = 1",
        (crew_id,),
    ).fetchone()
    if crew_row is None:
        return None

    start_dt = _parse_iso_utc(payload.sleep_start_utc)
    end_dt = _parse_iso_utc(payload.sleep_end_utc)
    if end_dt <= start_dt:
        raise ValueError("sleep_end_utc must be strictly after sleep_start_utc.")

    bouts_to_insert: list[tuple[SleepStageType, datetime, datetime, int]] = []
    if payload.stages:
        totals: dict[SleepStageType, int] = {"DEEP": 0, "REM": 0, "LIGHT": 0, "AWAKE": 0}
        for item in payload.stages:
            b_start = _parse_iso_utc(item.start_utc)
            b_end = _parse_iso_utc(item.end_utc)
            if b_end <= b_start:
                raise ValueError("Each sleep stage bout must have end_utc after start_utc.")
            dur = (
                item.duration_min
                if item.duration_min is not None
                else max(1, int(round((b_end - b_start).total_seconds() / 60.0)))
            )
            totals[item.stage] += dur
            bouts_to_insert.append((item.stage, b_start, b_end, dur))
        deep_min = payload.deep_min if payload.deep_min is not None else totals["DEEP"]
        rem_min = payload.rem_min if payload.rem_min is not None else totals["REM"]
        light_min = payload.light_min if payload.light_min is not None else totals["LIGHT"]
        awake_min = payload.awake_min if payload.awake_min is not None else totals["AWAKE"]
    else:
        bed_span = max(30, int(round((end_dt - start_dt).total_seconds() / 60.0)))
        if payload.deep_min is not None:
            deep_min = payload.deep_min
            rem_min = payload.rem_min or 0
            light_min = payload.light_min or 0
            awake_min = payload.awake_min or 0
        else:
            awake_min = max(10, round(bed_span * 0.06))
            asleep_span = max(20, bed_span - awake_min)
            deep_min = round(asleep_span * 0.22)
            rem_min = round(asleep_span * 0.25)
            light_min = max(10, asleep_span - deep_min - rem_min)
        bouts_to_insert = _build_ultradian_bouts(
            start_dt, deep_min, rem_min, light_min, awake_min
        )

    total_sleep_min = deep_min + rem_min + light_min
    span_bed_min = max(1, int(round((end_dt - start_dt).total_seconds() / 60.0)))
    time_in_bed_min = max(span_bed_min, total_sleep_min + awake_min)
    efficiency_pct = round(min(100.0, (total_sleep_min / time_in_bed_min) * 100.0), 1)
    sleep_score = (
        payload.sleep_score
        if payload.sleep_score is not None
        else _compute_sleep_score(total_sleep_min, efficiency_pct, deep_min, rem_min)
    )

    recorded_iso = _fmt_iso(end_dt)
    cur = conn.execute(
        """
        INSERT INTO sleep_sessions (
            crew_id, mission_stage, sleep_start_utc, sleep_end_utc,
            total_sleep_min, time_in_bed_min, sleep_score, sleep_efficiency_pct,
            deep_min, rem_min, light_min, awake_min, recorded_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            crew_id,
            payload.mission_stage,
            _fmt_iso(start_dt),
            _fmt_iso(end_dt),
            total_sleep_min,
            time_in_bed_min,
            sleep_score,
            efficiency_pct,
            deep_min,
            rem_min,
            light_min,
            awake_min,
            recorded_iso,
        ),
    )
    session_id = int(cur.lastrowid)
    conn.executemany(
        """
        INSERT INTO sleep_stages (session_id, stage, start_utc, end_utc, duration_min)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (session_id, st, _fmt_iso(s_dt), _fmt_iso(e_dt), dur)
            for st, s_dt, e_dt, dur in bouts_to_insert
        ],
    )
    update_streaks(conn, crew_id, recorded_iso[:10])
    conn.commit()

    return SleepSessionCreatedOut(
        session_id=session_id,
        crew_id=crew_id,
        mission_stage=payload.mission_stage,
        sleep_start_utc=_fmt_iso(start_dt),
        sleep_end_utc=_fmt_iso(end_dt),
        total_sleep_min=total_sleep_min,
        time_in_bed_min=time_in_bed_min,
        sleep_score=sleep_score,
        sleep_efficiency_pct=efficiency_pct,
        bouts_inserted=len(bouts_to_insert),
    )


def _format_stage_intervals(
    stage: SleepStageType,
    bouts: list[dict[str, Any]],
    cycle_count: int,
    win_start_hm: str,
    win_end_hm: str,
    period: SleepPeriod,
    nights_count: int,
) -> str:
    if not bouts:
        return "No bouts recorded in selected window"
    if stage == "LIGHT" and len(bouts) > 4:
        return (
            f"{len(bouts)} transition lapses across Cycles 1–{cycle_count} "
            f"({win_start_hm} – {win_end_hm} UTC)"
        )
    parts: list[str] = []
    for bout in bouts[:4]:
        parts.append(f"{bout['start_hm']}–{bout['end_hm']} ({bout['duration_min']}m)")
    joined = " · ".join(parts)
    if period != "last_night" and nights_count > 1:
        return f"Latest night: {joined}"
    return joined


def build_sleep_monitor(
    conn: sqlite3.Connection,
    crew_id: str,
    period: SleepPeriod = "last_night",
) -> SleepMonitorOut | None:
    crew_row = conn.execute(
        "SELECT id, code FROM crew_members WHERE id = ? AND is_active = 1",
        (crew_id,),
    ).fetchone()
    if crew_row is None:
        return None

    ensure_sleep_history(conn, crew_id)

    limit_nights = PERIOD_DAYS_MAP[period]
    sessions = conn.execute(
        """
        SELECT *
        FROM sleep_sessions
        WHERE crew_id = ?
        ORDER BY sleep_start_utc DESC, id DESC
        LIMIT ?
        """,
        (crew_id, limit_nights),
    ).fetchall()

    mission_row = conn.execute("SELECT launch_utc FROM mission WHERE id = 1").fetchone()
    launch_dt = (
        _parse_iso_utc(str(mission_row["launch_utc"]))
        if mission_row
        else datetime(2026, 10, 1, tzinfo=UTC)
    )

    if not sessions:
        now_dt = datetime.now(UTC)
        fallback_in = SleepSessionCreateIn(
            crew_id=crew_id,
            mission_stage="MISSION",
            sleep_start_utc=_fmt_iso(now_dt - timedelta(hours=8)),
            sleep_end_utc=_fmt_iso(now_dt - timedelta(minutes=24)),
        )
        create_sleep_session(conn, fallback_in)
        sessions = conn.execute(
            "SELECT * FROM sleep_sessions WHERE crew_id = ? ORDER BY id DESC LIMIT ?",
            (crew_id, limit_nights),
        ).fetchall()

    latest = sessions[0]
    latest_end_dt = _parse_iso_utc(str(latest["sleep_end_utc"]))
    latest_start_dt = _parse_iso_utc(str(latest["sleep_start_utc"]))
    mission_day = max(1, (latest_end_dt.date() - launch_dt.date()).days + 1)

    nights_count = len(sessions)
    avg_score = int(round(sum(int(s["sleep_score"]) for s in sessions) / nights_count))
    avg_sleep_min = int(round(sum(int(s["total_sleep_min"]) for s in sessions) / nights_count))
    avg_bed_min = int(round(sum(int(s["time_in_bed_min"]) for s in sessions) / nights_count))
    avg_eff_pct = int(round(sum(float(s["sleep_efficiency_pct"]) for s in sessions) / nights_count))
    avg_deep_min = int(round(sum(int(s["deep_min"]) for s in sessions) / nights_count))
    avg_rem_min = int(round(sum(int(s["rem_min"]) for s in sessions) / nights_count))
    avg_light_min = int(round(sum(int(s["light_min"]) for s in sessions) / nights_count))
    avg_awake_min = int(round(sum(int(s["awake_min"]) for s in sessions) / nights_count))

    if avg_score >= 80:
        quality_word = "Optimal"
        quality_tag = "OPTIMAL"
        quality_tone: HudTagTone = "reference"
    elif avg_score >= 65:
        quality_word = "Moderate"
        quality_tag = "MODERATE"
        quality_tone = "warn"
    else:
        quality_word = "Sleep Debt"
        quality_tag = "SLEEP DEBT"
        quality_tone = "critical"

    sleep_denom = max(1, avg_sleep_min)
    bed_denom = max(1, avg_bed_min)
    deep_pct = int(round((avg_deep_min / sleep_denom) * 100))
    rem_pct = int(round((avg_rem_min / sleep_denom) * 100))
    light_pct = max(0, 100 - deep_pct - rem_pct)
    awake_pct = int(round((avg_awake_min / bed_denom) * 100))

    raw_stages = conn.execute(
        """
        SELECT stage, start_utc, end_utc, duration_min
        FROM sleep_stages
        WHERE session_id = ?
        ORDER BY start_utc ASC, id ASC
        """,
        (int(latest["id"]),),
    ).fetchall()

    ribbon_bouts: list[SleepRibbonBoutOut] = []
    stage_buckets: dict[SleepStageType, list[dict[str, Any]]] = {
        "DEEP": [],
        "REM": [],
        "LIGHT": [],
        "AWAKE": [],
    }
    prev_lane: int | None = None
    max_offset_min = max(60.0, (latest_end_dt - latest_start_dt).total_seconds() / 60.0)

    for row in raw_stages:
        st_type: SleepStageType = row["stage"]
        b_start = _parse_iso_utc(str(row["start_utc"]))
        b_end = _parse_iso_utc(str(row["end_utc"]))
        start_off = max(0.0, round((b_start - latest_start_dt).total_seconds() / 60.0, 1))
        dur_m = max(1, int(row["duration_min"]))
        end_off = round(start_off + dur_m, 1)
        if end_off > max_offset_min:
            max_offset_min = end_off

        lane = STAGE_LANE_MAP[st_type]
        s_hm = b_start.strftime("%H:%M")
        e_hm = b_end.strftime("%H:%M")
        ribbon_bouts.append(
            SleepRibbonBoutOut(
                stage=st_type,
                lane_index=lane,
                prev_lane_index=prev_lane,
                start_offset_min=start_off,
                end_offset_min=end_off,
                duration_min=dur_m,
                start_hm=s_hm,
                end_hm=e_hm,
            )
        )
        stage_buckets[st_type].append(
            {"start_hm": s_hm, "end_hm": e_hm, "duration_min": dur_m}
        )
        prev_lane = lane

    awake_bouts_cnt = len(stage_buckets["AWAKE"])
    rem_bouts_cnt = len(stage_buckets["REM"])
    cycle_count = max(1, rem_bouts_cnt if rem_bouts_cnt > 0 else round(avg_sleep_min / 90.0))

    deep_ok = 16 <= deep_pct <= 28
    rem_ok = 18 <= rem_pct <= 28
    light_ok = 42 <= light_pct <= 60
    awake_ok = avg_awake_min <= 35

    stage_cards: list[SleepStageCardOut] = [
        SleepStageCardOut(
            stage="DEEP",
            label="Deep Sleep",
            duration_min=avg_deep_min,
            duration_display=_fmt_hm(avg_deep_min),
            badge_label="Restorative" if deep_ok else "Reduced",
            badge_tone="reference" if deep_ok else "warn",
            share_pct=deep_pct,
            subtitle=f"{deep_pct}% of sleep · Target 18–25%",
            bar_fill_pct=min(100.0, round((deep_pct / 28.0) * 100.0, 1)),
        ),
        SleepStageCardOut(
            stage="REM",
            label="REM Sleep",
            duration_min=avg_rem_min,
            duration_display=_fmt_hm(avg_rem_min),
            badge_label="Optimal" if rem_ok else "Reduced",
            badge_tone="reference" if rem_ok else "warn",
            share_pct=rem_pct,
            subtitle=f"{rem_pct}% of sleep · Target 20–25%",
            bar_fill_pct=min(100.0, round((rem_pct / 28.0) * 100.0, 1)),
        ),
        SleepStageCardOut(
            stage="LIGHT",
            label="Light Sleep",
            duration_min=avg_light_min,
            duration_display=_fmt_hm(avg_light_min),
            badge_label="Balanced" if light_ok else "Shifted",
            badge_tone="reference" if light_ok else "warn",
            share_pct=light_pct,
            subtitle=f"{light_pct}% of sleep · Normal 45–55%",
            bar_fill_pct=min(100.0, round((light_pct / 75.0) * 100.0, 1)),
        ),
        SleepStageCardOut(
            stage="AWAKE",
            label="Awake Time",
            duration_min=avg_awake_min,
            duration_display=_fmt_hm(avg_awake_min),
            badge_label=f"{awake_bouts_cnt} Brief" if awake_ok else "Fragmented",
            badge_tone="reference" if awake_ok else "warn",
            share_pct=awake_pct,
            subtitle=f"{awake_pct}% in bed · Limit < 0h 35m",
            bar_fill_pct=min(100.0, round((avg_awake_min / 60.0) * 100.0, 1)),
        ),
    ]

    axis_ticks: list[SleepAxisTickOut] = []
    tick_step = 60
    tick_cursor = 0.0
    while tick_cursor <= max_offset_min:
        t_dt = latest_start_dt + timedelta(minutes=tick_cursor)
        axis_ticks.append(SleepAxisTickOut(offset_min=tick_cursor, label=t_dt.strftime("%H:%M")))
        tick_cursor += tick_step
    if not axis_ticks or axis_ticks[-1].offset_min < max_offset_min:
        axis_ticks.append(
            SleepAxisTickOut(
                offset_min=round(max_offset_min, 1),
                label=latest_end_dt.strftime("%H:%M"),
            )
        )

    win_start_hm = latest_start_dt.strftime("%H:%M")
    win_end_hm = latest_end_dt.strftime("%H:%M")

    stage_meta: list[tuple[SleepStageType, str, int]] = [
        ("DEEP", "Deep Sleep", avg_deep_min),
        ("REM", "REM Sleep", avg_rem_min),
        ("LIGHT", "Light Sleep", avg_light_min),
        ("AWAKE", "Awake", avg_awake_min),
    ]
    lapse_rows: list[SleepStageLapseRowOut] = []
    for st_key, st_label, avg_total_m in stage_meta:
        b_list = stage_buckets[st_key]
        b_cnt = len(b_list)
        if b_cnt > 0:
            avg_b = int(round(sum(x["duration_min"] for x in b_list) / b_cnt))
            max_b = max(x["duration_min"] for x in b_list)
            avg_max_str = f"Avg {avg_b}m · Max {max_b}m"
        else:
            avg_max_str = "Avg 0m · Max 0m"

        lapse_rows.append(
            SleepStageLapseRowOut(
                stage=st_key,
                label=st_label,
                intervals_summary=_format_stage_intervals(
                    st_key,
                    b_list,
                    cycle_count,
                    win_start_hm,
                    win_end_hm,
                    period,
                    nights_count,
                ),
                bouts_count=b_cnt,
                bouts_label=f"{b_cnt} bout" if b_cnt == 1 else f"{b_cnt} bouts",
                avg_max_label=avg_max_str,
                total_display=_fmt_hm(avg_total_m),
            )
        )

    latest_deep_m = int(latest["deep_min"])
    latest_rem_m = int(latest["rem_min"])
    latest_light_m = int(latest["light_min"])
    latest_awake_m = int(latest["awake_min"])

    ribbon_legend: list[SleepRibbonLegendItemOut] = [
        SleepRibbonLegendItemOut(stage="AWAKE", label=f"Awake ({_fmt_short_min(latest_awake_m)})"),
        SleepRibbonLegendItemOut(stage="REM", label=f"REM ({_fmt_short_min(latest_rem_m)})"),
        SleepRibbonLegendItemOut(stage="LIGHT", label=f"Light ({_fmt_short_min(latest_light_m)})"),
        SleepRibbonLegendItemOut(stage="DEEP", label=f"Deep ({_fmt_short_min(latest_deep_m)})"),
    ]

    target_met = avg_sleep_min >= 420
    heading = (
        "TOTAL SLEEP TIME"
        if period == "last_night"
        else f"AVG SLEEP TIME · {nights_count} NIGHTS"
    )
    ribbon_prefix = (
        "SLEEP STAGE RIBBON CHART"
        if period == "last_night"
        else "LATEST NIGHT RIBBON HYPNOGRAM"
    )

    return SleepMonitorOut(
        crew_id=str(crew_row["id"]),
        crew_code=str(crew_row["code"]),
        period=period,
        nights_analyzed=nights_count,
        mission_day=mission_day,
        last_night_tab_label=f"Last Night (D{mission_day:02d})",
        rest_window_badge=f"REST WINDOW · {win_start_hm} – {win_end_hm} UTC",
        header_score_badge=f"SCORE {avg_score} · {quality_tag}",
        quality_tag=quality_tag,
        quality_tone=quality_tone,
        sleep_score=avg_score,
        score_subtitle=f"of 100 · {quality_word}",
        sleep_time_heading=heading,
        total_sleep_min=avg_sleep_min,
        total_sleep_display=_fmt_hm(avg_sleep_min),
        target_label="Target ≥ 7h 00m Met" if target_met else "Below ≥ 7h 00m Target",
        target_met=target_met,
        in_bed_min=avg_bed_min,
        in_bed_display=f"In Bed: {_fmt_hm(avg_bed_min)}",
        efficiency_pct=avg_eff_pct,
        efficiency_label=f"Sleep Efficiency: {avg_eff_pct}%",
        stage_cards=stage_cards,
        ribbon_title=f"{ribbon_prefix} · {win_start_hm} – {win_end_hm} UTC",
        cycle_count=cycle_count,
        cycle_badge=f"{cycle_count} CYCLES",
        rest_window_inline=f"REST WINDOW: {win_start_hm} – {win_end_hm} UTC",
        window_total_min=round(max_offset_min, 1),
        axis_ticks=axis_ticks,
        ribbon_legend=ribbon_legend,
        ribbon_bouts=ribbon_bouts,
        total_bouts=len(ribbon_bouts),
        bouts_badge=f"{len(ribbon_bouts)} BOUTS LOGGED",
        lapse_rows=lapse_rows,
    )
