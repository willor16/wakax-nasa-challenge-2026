"""Psychological check-ins and the 2-minute reaction test (D3-03).

Pure scoring functions first (testable without a database), then storage and the
read-only profile used by screen 05.

Science:
* Behavioral scales are 1-5 self-ratings (mood, stress, isolation, motivation).
  The wellbeing index averages them on a 0-100 scale with stress and isolation
  reversed, so 100 is the best possible day.
* The reaction test follows the Psychomotor Vigilance Task: a response under
  100 ms (or with no stimulus on screen) is a false start and a response of
  500 ms or more, or none at all, is a lapse (Dinges & Powell, Behavior Research
  Methods 17:652-655, 1985; Basner & Dinges, Sleep 34(5):581-591, 2011). The
  vigilance score is 100 x (1 - (lapses + false starts) / (valid stimuli +
  false starts)), the PVT performance score proposed by Basner & Dinges.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean

from app.services.alert_engine import raise_wellbeing_alert
from app.services.alert_rules import Severity
from app.services.mission_clock import day_label, mission_day, parse_iso

MOOD_STATES = ("CALM", "FOCUSED", "TIRED", "STRESSED")
FALSE_START_MS = 100
LAPSE_MS = 500
REACTION_TARGET_MS = 300          # screen 05/13: "Optimal threshold < 300 ms"
PRECISION_TARGET_PCT = 95.0       # screen 05: "Target accuracy >= 95%"
OPTIMAL_ZONE = (3.8, 5.0)         # screen 05: "Optimal wellbeing zone (3.8 - 5.0)"
STRESS_TARGET = 40                # screen 05: "Target range: < 40" (0-100)
ISOLATION_TARGET = 2.5            # screen 05: "Target range: < 2.5"
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


# ---------------------------------------------------------------- scoring ---

def wellbeing_index(mood: int, stress: int, isolation: int, motivation: int) -> float:
    """0-100 average of the four 1-5 scales, with stress and isolation reversed."""
    parts = [mood - 1, 5 - stress, 5 - isolation, motivation - 1]
    return round(sum(parts) / 16 * 100, 1)


def stress_index(stress: float) -> int:
    """Stress on the 0-100 scale shown on screen 05 (1 -> 0, 5 -> 100)."""
    return round((stress - 1) / 4 * 100)


def calmness(stress: float) -> float:
    """Calmness on the 1-5 scale used in the 14-day trend (the mirror of stress)."""
    return round(6 - stress, 2)


@dataclass(frozen=True, slots=True)
class ReactionResult:
    trials_total: int
    valid_responses: int
    false_starts: int
    lapses: int
    reaction_ms: float
    accuracy_pct: float
    attention_score: float


def score_reaction_test(reaction_times_ms: list[float | None], false_starts: int
                        ) -> ReactionResult:
    """Score one session. ``None`` means the stimulus got no response (a lapse).

    ``false_starts`` counts taps with no stimulus on screen; responses under
    100 ms are also counted as false starts.
    """
    early = [t for t in reaction_times_ms if t is not None and t < FALSE_START_MS]
    answered = [t for t in reaction_times_ms if t is not None and t >= FALSE_START_MS]
    missed = sum(1 for t in reaction_times_ms if t is None)
    slow = [t for t in answered if t >= LAPSE_MS]
    valid = [t for t in answered if t < LAPSE_MS]

    stimuli = len(reaction_times_ms)
    total_false = false_starts + len(early)
    lapses = missed + len(slow)
    attempts = stimuli + false_starts
    accuracy = 100.0 * len(valid) / attempts if attempts else 0.0
    # Basner & Dinges 2011: errors relative to valid stimuli plus false starts.
    # A response under 100 ms is a false start, not a valid stimulus, so the
    # denominator is every stimulus plus the taps made with nothing on screen.
    chances = stimuli + false_starts
    vigilance = 100.0 * (1 - (lapses + total_false) / chances) if chances else 0.0
    return ReactionResult(
        trials_total=stimuli,
        valid_responses=len(valid),
        false_starts=total_false,
        lapses=lapses,
        reaction_ms=round(mean(answered), 1) if answered else 0.0,
        accuracy_pct=round(max(0.0, accuracy), 1),
        attention_score=round(max(0.0, min(100.0, vigilance)), 1),
    )


def stability_pct(daily_moods: list[float]) -> int:
    """Share of logged days inside the optimal wellbeing zone."""
    if not daily_moods:
        return 0
    low, high = OPTIMAL_ZONE
    inside = sum(1 for m in daily_moods if low <= m <= high)
    return round(100 * inside / len(daily_moods))


# ---------------------------------------------------------------- storage ---

_EXTRA_COLUMNS = {
    "psych_tests": {
        "mood_state": "TEXT CHECK (mood_state IS NULL OR mood_state IN "
                      "('CALM', 'FOCUSED', 'TIRED', 'STRESSED'))",
        "sleep_onset_utc": "TEXT",
        "wake_utc": "TEXT",
    },
    "cognitive_tests": {
        "trials_total": "INTEGER NOT NULL DEFAULT 0 CHECK (trials_total >= 0)",
        "valid_responses": "INTEGER NOT NULL DEFAULT 0 CHECK (valid_responses >= 0)",
        "false_starts": "INTEGER NOT NULL DEFAULT 0 CHECK (false_starts >= 0)",
        "lapses": "INTEGER NOT NULL DEFAULT 0 CHECK (lapses >= 0)",
    },
}


def ensure_mind_columns(conn: sqlite3.Connection) -> None:
    """Add the screen 13 columns to databases created before they existed."""
    for table, columns in _EXTRA_COLUMNS.items():
        present = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, ddl in columns.items():
            if name not in present:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _now() -> str:
    return datetime.now(UTC).strftime(TS_FORMAT)


def _mission_stage(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT current_stage FROM mission WHERE id = 1").fetchone()
    return row["current_stage"] if row else "MISSION"


def save_checkin(conn: sqlite3.Connection, crew_id: str, *, mood_state: str | None,
                 mood: int, stress: int, isolation: int, motivation: int,
                 sleep_onset_utc: str | None = None, wake_utc: str | None = None,
                 recorded_at_utc: str | None = None) -> dict:
    """Store one behavioral check-in and return it with its wellbeing index."""
    index = wellbeing_index(mood, stress, isolation, motivation)
    stamp = recorded_at_utc or _now()
    cursor = conn.execute(
        """
        INSERT INTO psych_tests (
            crew_id, mission_stage, mood_score, stress_score, loneliness_score,
            motivation_score, wellbeing_index, recorded_at_utc, mood_state,
            sleep_onset_utc, wake_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (crew_id, _mission_stage(conn), mood, stress, isolation, motivation, index, stamp,
         mood_state, sleep_onset_utc, wake_utc),
    )
    alert_id = _checkin_alert(conn, crew_id, mood, stress, isolation, motivation, stamp)
    return {"id": int(cursor.lastrowid), "wellbeing_index": index, "recorded_at_utc": stamp,
            "alert_id": alert_id}


def _checkin_alert(conn: sqlite3.Connection, crew_id: str, mood: int, stress: int,
                   isolation: int, motivation: int, stamp: str) -> int | None:
    """A hard day deserves support: raise a wellbeing advisory for the crew member."""
    concerns = []
    if stress >= 4:
        concerns.append("high stress")
    if mood <= 2:
        concerns.append("low mood")
    if isolation >= 4:
        concerns.append("feeling isolated")
    if motivation <= 2:
        concerns.append("low motivation")
    if not concerns:
        return None
    worst = stress == 5 or mood == 1 or isolation == 5 or len(concerns) >= 2
    severity = Severity.WARNING if worst else Severity.INFO
    title = f"Wellbeing check-in: {' and '.join(concerns[:2])}"
    message = ("Today's check-in is outside your usual range. "
               "Small steps help; the crew physician is there to talk.")
    return raise_wellbeing_alert(conn, crew_id, severity, title, message, "wellbeing", stamp)


def save_reaction_session(conn: sqlite3.Connection, crew_id: str,
                          reaction_times_ms: list[float | None], false_starts: int,
                          duration_sec: int = 120, recorded_at_utc: str | None = None
                          ) -> dict:
    """Score and store one reaction test session."""
    result = score_reaction_test(reaction_times_ms, false_starts)
    stamp = recorded_at_utc or _now()
    cursor = conn.execute(
        """
        INSERT INTO cognitive_tests (
            crew_id, mission_stage, test_type, reaction_ms, accuracy_pct, attention_score,
            duration_sec, recorded_at_utc, trials_total, valid_responses, false_starts, lapses
        ) VALUES (?, ?, 'REACTION_ARENA', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (crew_id, _mission_stage(conn), result.reaction_ms or 1.0, result.accuracy_pct,
         result.attention_score, duration_sec, stamp, result.trials_total,
         result.valid_responses, result.false_starts, result.lapses),
    )
    alert_id = None
    slow = result.valid_responses > 0 and result.reaction_ms >= REACTION_TARGET_MS
    if slow or result.lapses >= 3 or result.accuracy_pct < PRECISION_TARGET_PCT - 10:
        role = conn.execute("SELECT role FROM crew_members WHERE id = ?", (crew_id,)).fetchone()
        pilot = bool(role) and role["role"] == "PILOT"
        severity = Severity.WARNING if (pilot or result.lapses >= 5) else Severity.INFO
        message = (f"Mean reaction {result.reaction_ms:g} ms with {result.lapses} lapses "
                   f"(target under {REACTION_TARGET_MS} ms).")
        if pilot:
            message += " Important for piloting."
        alert_id = raise_wellbeing_alert(conn, crew_id, severity, "Reaction test below target",
                                         message, "alertness", stamp, category="ALERTNESS")
    return {"id": int(cursor.lastrowid), "recorded_at_utc": stamp, "alert_id": alert_id,
            **asdict(result)}


# ---------------------------------------------------------------- profile ---

def _band(value: float, low: float, high: float) -> str:
    """Plain label for a 1-5 positive scale against the personal range."""
    if value > high:
        return "High"
    if value >= low:
        return "Positive"
    return "Low"


def _reference_range(conn: sqlite3.Connection, crew_id: str, column: str, day: str
                     ) -> tuple[tuple[float, float], str]:
    """Range a 1-5 scale is compared against, and where that range comes from.

    The latest day is never part of its own reference. In order: the pre-flight
    check-ins (``BASELINE``), the days logged before the latest one (``RECENT``),
    and with no earlier data the optimal wellbeing zone (``OPTIMAL_ZONE``).
    """
    assert column in ("mood_score", "motivation_score")
    for source, where in (("BASELINE", "mission_stage = 'LAUNCH'"), ("RECENT", "1 = 1")):
        row = conn.execute(
            f"SELECT MIN({column}) AS low, MAX({column}) AS high FROM psych_tests"
            f" WHERE crew_id = ? AND substr(recorded_at_utc, 1, 10) < ? AND {where}",
            (crew_id, day),
        ).fetchone()
        if row["low"] is not None:
            return (float(row["low"]), float(row["high"])), source
    return OPTIMAL_ZONE, "OPTIMAL_ZONE"


def psych_profile(conn: sqlite3.Connection, crew_id: str, days: int = 14,
                  now: datetime | None = None) -> dict:
    """Read-only data for screen 05: latest state, 14-day trend and reaction results."""
    now = now or datetime.now(UTC)
    newest = conn.execute(
        "SELECT MAX(recorded_at_utc) FROM psych_tests WHERE crew_id = ?", (crew_id,)
    ).fetchone()[0]
    if newest:  # the 14-day window ends on the last logged day
        now = min(now, parse_iso(newest))
    since = (now - timedelta(days=days - 1)).strftime("%Y-%m-%dT00:00:00Z")
    rows = conn.execute(
        """
        SELECT substr(recorded_at_utc, 1, 10) AS day,
               AVG(mood_score) AS mood, AVG(stress_score) AS stress,
               AVG(loneliness_score) AS isolation, AVG(motivation_score) AS motivation
        FROM psych_tests
        WHERE crew_id = ? AND recorded_at_utc >= ?
        GROUP BY day ORDER BY day
        """,
        (crew_id, since),
    ).fetchall()
    trend = [
        {"day": r["day"],
         "day_label": day_label(mission_day(conn, parse_iso(f"{r['day']}T00:00:00Z"))),
         "mood": round(r["mood"], 2), "calmness": calmness(r["stress"])}
        for r in rows
    ]

    latest_row = conn.execute(
        "SELECT * FROM psych_tests WHERE crew_id = ? ORDER BY recorded_at_utc DESC, id DESC"
        " LIMIT 1",
        (crew_id,),
    ).fetchone()
    scales = None
    if rows:
        today = rows[-1]
        mood_range, mood_source = _reference_range(conn, crew_id, "mood_score", today["day"])
        mot_range, mot_source = _reference_range(conn, crew_id, "motivation_score",
                                                 today["day"])
        stress_value = stress_index(today["stress"])
        scales = {
            "mood": {"value": round(today["mood"], 1), "range": mood_range,
                     "range_source": mood_source,
                     "label": _band(today["mood"], *mood_range)},
            "stress_index": {"value": stress_value, "target_below": STRESS_TARGET,
                             "label": "Low" if stress_value < STRESS_TARGET else "High"},
            "isolation": {"value": round(today["isolation"], 1), "target_below": ISOLATION_TARGET,
                          "label": "Low" if today["isolation"] < ISOLATION_TARGET else "High"},
            "motivation": {"value": round(today["motivation"], 1), "range": mot_range,
                           "range_source": mot_source,
                           "label": _band(today["motivation"], *mot_range)},
        }

    session = conn.execute(
        "SELECT * FROM cognitive_tests WHERE crew_id = ? ORDER BY recorded_at_utc DESC, id DESC"
        " LIMIT 1",
        (crew_id,),
    ).fetchone()
    reaction = None
    if session is not None:
        answered = session["valid_responses"] > 0 or session["trials_total"] == 0
        reaction = {
            # A session with no valid answer has no meaningful reaction time.
            "reaction_ms": session["reaction_ms"] if answered else None,
            "reaction_target_ms": REACTION_TARGET_MS,
            "accuracy_pct": session["accuracy_pct"],
            "accuracy_target_pct": PRECISION_TARGET_PCT,
            "attention_score": session["attention_score"],
            "lapses": session["lapses"],
            "false_starts": session["false_starts"],
            "trials_total": session["trials_total"],
            "valid_responses": session["valid_responses"],
            "recorded_at_utc": session["recorded_at_utc"],
        }

    daily_moods = [t["mood"] for t in trend]
    return {
        "crew_id": crew_id,
        "latest_state": None if latest_row is None else {
            "mood_state": latest_row["mood_state"],
            "recorded_at_utc": latest_row["recorded_at_utc"],
            "wellbeing_index": latest_row["wellbeing_index"],
        },
        "scales": scales,
        "trend": trend,
        "optimal_zone": list(OPTIMAL_ZONE),
        "stability_pct": stability_pct(daily_moods),
        "reaction": reaction,
    }
