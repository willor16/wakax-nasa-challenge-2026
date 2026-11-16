"""Flight & Docking Readiness for the pilot (M9).

Built only from what the crew logged on board: the reaction tests (attention, accuracy,
reaction time, lapses, false starts), sleep sessions and the visual acuity check. Nothing
is invented: a part that was never measured (working-memory retention, until its test
exists) is reported as not measured and left out of the score.

The pilot's thresholds are stricter than the rest of the crew's: manual flight and
docking need a score of 85 or more and at least six hours of sleep in the last day.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from statistics import mean, median, pstdev
from typing import Any

from app.services.clinical_view import metric_view
from app.services.mission_clock import parse_iso, to_iso, utc_now

RECENT_TESTS = 5
MEMORY_TESTS = ("MEMORY_SPAN", "RETENTION", "SEQUENCE_RECALL")
# Share of each part in the score; parts that were not measured are left out.
WEIGHTS = {"attention": 30, "focus": 25, "reaction": 20, "retention": 15, "sleep": 10}
CLEARED, CROSS_CHECK = 85, 70
SLEEP_GATE_H = 6.0
SLEEP_TARGET_H = 7.0
ACUITY_GATE = 30  # Snellen denominator: worse than 20/30 needs a cross-check
REACTION_BEST_MS, REACTION_WORST_MS = 250.0, 450.0
RECOVERY_MARGIN = 1.10

STATES = {
    "CLEARED": "CLEARED FOR MANUAL FLIGHT & DOCKING",
    "CROSS_CHECK": "CO-PILOT CROSS-CHECK REQUIRED",
    "RESTRICTED": "FLIGHT DUTY RESTRICTED · REST MANDATED",
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def reaction_score(reaction_ms: float) -> float:
    """250 ms or faster is full marks, 450 ms or slower is zero."""
    span = REACTION_WORST_MS - REACTION_BEST_MS
    return _clamp((REACTION_WORST_MS - reaction_ms) / span * 100)


def focus_index(accuracy: list[float], reaction: list[float], false_starts: list[int]) -> float:
    """Steady concentration: accurate answers, an even pace and no early taps."""
    spread = pstdev(reaction) if len(reaction) > 1 else 0.0
    steadiness = _clamp(100 - spread / mean(reaction) * 100 * 4) if reaction else 0.0
    early = _clamp(100 - mean(false_starts) * 10) if false_starts else 100.0
    return round(0.5 * mean(accuracy) + 0.3 * steadiness + 0.2 * early, 1)


def recovery_days(sessions: list[dict]) -> float | None:
    """Days the pilot needed to return to the usual reaction time after the slowest test
    (within 10%); None when there was no slow test or it has not recovered yet."""
    if len(sessions) < 3:
        return None
    usual = median(s["reaction_ms"] for s in sessions)  # one slow test does not move it
    worst = max(range(len(sessions)), key=lambda i: sessions[i]["reaction_ms"])
    if sessions[worst]["reaction_ms"] <= usual * RECOVERY_MARGIN:
        return 0.0
    for later in sessions[worst + 1:]:
        if later["reaction_ms"] <= usual * RECOVERY_MARGIN:
            slowest = parse_iso(sessions[worst]["recorded_at_utc"])
            gap = parse_iso(later["recorded_at_utc"]) - slowest
            return round(gap.total_seconds() / 86400, 1)
    return None


def _sleep_hours(conn: sqlite3.Connection, crew_id: str, hours: int) -> float | None:
    since = to_iso(utc_now() - timedelta(hours=hours))
    row = conn.execute(
        """SELECT COUNT(*) AS n, SUM(total_sleep_min) AS total FROM sleep_sessions
           WHERE crew_id = ? AND sleep_end_utc >= ?""",
        (crew_id, since),
    ).fetchone()
    return round(row["total"] / 60, 1) if row["n"] else None


def classify(score: float | None, sleep_24h: float | None, acuity: float | None) -> str:
    if score is None:
        return "CROSS_CHECK"
    if score < CROSS_CHECK or (sleep_24h is not None and sleep_24h < SLEEP_GATE_H):
        return "RESTRICTED"
    if score < CLEARED or (acuity is not None and acuity > ACUITY_GATE) or sleep_24h is None:
        return "CROSS_CHECK"
    return "CLEARED"


def pilot_readiness(conn: sqlite3.Connection, crew_id: str) -> dict[str, Any]:
    rows = conn.execute(
        """SELECT test_type, reaction_ms, accuracy_pct, attention_score, lapses, false_starts,
                  recorded_at_utc FROM cognitive_tests WHERE crew_id = ?
           ORDER BY recorded_at_utc ASC, id ASC""",
        (crew_id,),
    ).fetchall()
    reaction_tests = [dict(r) for r in rows if r["test_type"] not in MEMORY_TESTS]
    memory_tests = [dict(r) for r in rows if r["test_type"] in MEMORY_TESTS]
    recent = reaction_tests[-RECENT_TESTS:]

    parts: dict[str, float | None] = dict.fromkeys(WEIGHTS)
    attention = lapses = reaction_ms = focus = None
    if recent:
        attention = round(mean(r["attention_score"] for r in recent), 1)
        lapses = sum(r["lapses"] for r in recent)
        reaction_ms = round(mean(r["reaction_ms"] for r in recent))
        focus = focus_index([r["accuracy_pct"] for r in recent],
                            [r["reaction_ms"] for r in recent],
                            [r["false_starts"] for r in recent])
        parts.update(attention=attention, focus=focus, reaction=reaction_score(reaction_ms))
    retention = round(mean(r["accuracy_pct"] for r in memory_tests[-RECENT_TESTS:]), 1) \
        if memory_tests else None
    parts["retention"] = retention

    sleep_24h = _sleep_hours(conn, crew_id, 24)
    sleep_48h = _sleep_hours(conn, crew_id, 48)
    if sleep_24h is not None:
        parts["sleep"] = _clamp(sleep_24h / SLEEP_TARGET_H * 100)
    acuity_view = metric_view(conn, crew_id, "visual_acuity_snellen")
    acuity = acuity_view["value"]

    measured = {k: v for k, v in parts.items() if v is not None}
    score = (round(sum(v * WEIGHTS[k] for k, v in measured.items())
                   / sum(WEIGHTS[k] for k in measured)) if measured else None)
    state = classify(score, sleep_24h, acuity)

    reasons = []
    if sleep_24h is not None and sleep_24h < SLEEP_GATE_H:
        reasons.append(f"Only {sleep_24h:g} h of sleep in the last 24 h (6 h needed).")
    if sleep_24h is None:
        reasons.append("No sleep logged in the last 24 h.")
    if acuity is not None and acuity > ACUITY_GATE:
        reasons.append(f"Visual acuity 20/{acuity:g} is below the 20/30 flight standard.")
    if score is not None and score < CLEARED:
        reasons.append(f"Readiness score {score} is under 85.")

    return {
        "crew_id": crew_id,
        "score": score,
        "state": state,
        "state_en": STATES[state],
        "reasons_en": reasons,
        "retention": {"cognitive_retention_pct": retention,
                      "measured": retention is not None,
                      "note_en": None if retention is not None else "Not measured yet"},
        "attention": {"sustained_attention_pct": attention, "attention_lapses": lapses},
        "focus": {"focus_index_score": focus},
        "sensorimotor": {"reaction_time_ms": reaction_ms,
                         "recovery_days": recovery_days(reaction_tests[-14:])},
        "gate": {"visual_acuity_snellen": acuity,
                 "visual_acuity_text": f"20/{acuity:g}" if acuity is not None else None,
                 "sleep_24h_h": sleep_24h, "sleep_48h_h": sleep_48h},
        "tests_used": len(recent),
        "last_test_utc": recent[-1]["recorded_at_utc"] if recent else None,
        "history": [
            {"recorded_at_utc": r["recorded_at_utc"],
             "attention": r["attention_score"],
             "focus": focus_index([r["accuracy_pct"]], [r["reaction_ms"]], [r["false_starts"]]),
             "reaction_ms": r["reaction_ms"]}
            for r in reaction_tests[-30:]
        ],
    }
