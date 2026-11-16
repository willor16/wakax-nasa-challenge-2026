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

import json
import math
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Any

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
        "assessment_type": "TEXT NOT NULL DEFAULT 'DAILY_CHECKIN'",
        "payload_json": "TEXT NOT NULL DEFAULT '{}'",
    },
    "cognitive_tests": {
        "trials_total": "INTEGER NOT NULL DEFAULT 0 CHECK (trials_total >= 0)",
        "valid_responses": "INTEGER NOT NULL DEFAULT 0 CHECK (valid_responses >= 0)",
        "false_starts": "INTEGER NOT NULL DEFAULT 0 CHECK (false_starts >= 0)",
        "lapses": "INTEGER NOT NULL DEFAULT 0 CHECK (lapses >= 0)",
        "payload_json": "TEXT NOT NULL DEFAULT '{}'",
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
    ensure_mind_columns(conn)
    index = wellbeing_index(mood, stress, isolation, motivation)
    stamp = recorded_at_utc or _now()
    cursor = conn.execute(
        """
        INSERT INTO psych_tests (
            crew_id, mission_stage, mood_score, stress_score, loneliness_score,
            motivation_score, wellbeing_index, recorded_at_utc, mood_state,
            sleep_onset_utc, wake_utc, assessment_type, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DAILY_CHECKIN', '{}')
        """,
        (crew_id, _mission_stage(conn), mood, stress, isolation, motivation, index, stamp,
         mood_state, sleep_onset_utc, wake_utc),
    )
    alert_id = _checkin_alert(conn, crew_id, mood, stress, isolation, motivation, stamp)
    return {"id": int(cursor.lastrowid), "wellbeing_index": index, "recorded_at_utc": stamp,
            "alert_id": alert_id}


def _apa_severity(mean_val: float) -> tuple[str, int]:
    if mean_val < 0.5:
        return "None (APA 0)", 0
    if mean_val < 1.5:
        return "Mild (APA 1)", 1
    if mean_val < 2.5:
        return "Moderate (APA 2)", 2
    if mean_val < 3.5:
        return "Severe (APA 3)", 3
    return "Extreme (APA 4)", 4


def _phq9_category(score: int) -> str:
    if score >= 20:
        return "Severe (20-27)"
    if score >= 15:
        return "Moderately Severe (15-19)"
    if score >= 10:
        return "Moderate (10-14)"
    if score >= 5:
        return "Mild (5-9)"
    return "Minimal or Absent (0-4)"


def score_behavioral_matrix(item_responses: list[int]) -> dict[str, Any]:
    if len(item_responses) != 20 or any(v < 0 or v > 4 for v in item_responses):
        raise ValueError("Behavioral matrix requires 20 integer responses between 0 and 4.")
    sub_indices = {
        "T": (0, 4, 8, 12),
        "D": (1, 5, 9, 13),
        "C": (2, 6, 10, 14),
        "F": (3, 7, 11, 15),
        "S": (16, 17, 18, 19),
    }
    sub_names = {
        "T": "Tension & Stress",
        "D": "Dejection & Motivation",
        "C": "Anger & Irritability",
        "F": "Fatigue & Exhaustion",
        "S": "Social Isolation",
    }
    sums = {code: sum(item_responses[i] for i in idxs) for code, idxs in sub_indices.items()}
    total_load = sum(sums.values())
    mean_load = round(total_load / 20, 2)
    if total_load <= 20:
        readiness = "FIT FOR FLIGHT"
        range_label = "Optimal State (0-20 pts)"
    elif total_load <= 40:
        readiness = "MONITORING REQUIRED"
        range_label = "Moderate Load (21-40 pts)"
    else:
        readiness = "RESTRICTED DUTY"
        range_label = "Critical Alert (41-80 pts)"

    gad_mean = round(sums["T"] / 4, 2)
    gad_scaled_40 = round(gad_mean * 10)
    gad_label, gad_level = _apa_severity(gad_mean)
    dep_mean = (sums["D"] * 0.65 + sums["F"] * 0.35) / 4
    phq9_eq = min(27, round((dep_mean / 4) * 27))
    phq9_cat = _phq9_category(phq9_eq)
    stage2_triggered = gad_mean >= 1.5 or phq9_eq >= 10 or sums["S"] >= 8

    elevated = [
        f"{sub_names[code]} ({code}={val}/16)" for code, val in sums.items() if val >= 8
    ]
    subscales = {
        code: {
            "label": sub_names[code],
            "score": sums[code],
            "max": 16,
            "apa_mean": round(sums[code] / 4, 2),
            "apa_label": _apa_severity(sums[code] / 4)[0],
        }
        for code in ("T", "D", "C", "F", "S")
    }
    mapped_stress = min(5, max(1, round(1 + (sums["T"] / 16) * 4)))
    mapped_isolation = min(5, max(1, round(1 + (sums["S"] / 16) * 4)))
    mapped_motivation = min(5, max(1, round(5 - (sums["D"] / 16) * 4)))
    mapped_mood = min(5, max(1, round(5 - (total_load / 80) * 4)))
    if total_load > 40 or sums["T"] >= 8 or sums["C"] >= 8:
        derived_state = "STRESSED"
    elif sums["F"] >= 8:
        derived_state = "TIRED"
    elif total_load > 20:
        derived_state = "FOCUSED"
    else:
        derived_state = "CALM"

    return {
        "total_load_score": total_load,
        "max_score": 80,
        "mean_item_score": mean_load,
        "readiness_status": readiness,
        "range_label": range_label,
        "subscales": subscales,
        "apa_crosswalk": {
            "gad_mean": gad_mean,
            "gad_scaled_40": gad_scaled_40,
            "gad_label": gad_label,
            "gad_level": gad_level,
            "phq9_eq": phq9_eq,
            "phq9_category": phq9_cat,
            "stage2_triggered": stage2_triggered,
        },
        "elevated_alerts": elevated,
        "item_responses": item_responses,
        "mapped_scales": {
            "mood": mapped_mood,
            "stress": mapped_stress,
            "isolation": mapped_isolation,
            "motivation": mapped_motivation,
            "mood_state": derived_state,
        },
    }


def save_behavioral_matrix(
    conn: sqlite3.Connection,
    crew_id: str,
    item_responses: list[int],
    *,
    mood_state: str | None = None,
    sleep_onset_utc: str | None = None,
    wake_utc: str | None = None,
    recorded_at_utc: str | None = None,
) -> dict[str, Any]:
    ensure_mind_columns(conn)
    report = score_behavioral_matrix(item_responses)
    mapped = report["mapped_scales"]
    mood = mapped["mood"]
    stress = mapped["stress"]
    isolation = mapped["isolation"]
    motivation = mapped["motivation"]
    state_tag = mood_state or mapped["mood_state"]
    index = wellbeing_index(mood, stress, isolation, motivation)
    stamp = recorded_at_utc or _now()
    payload = {
        "assessment_type": "BEHAVIORAL_MATRIX_20",
        "total_load_score": report["total_load_score"],
        "max_score": 80,
        "mean_item_score": report["mean_item_score"],
        "readiness_status": report["readiness_status"],
        "range_label": report["range_label"],
        "subscales": report["subscales"],
        "apa_crosswalk": report["apa_crosswalk"],
        "elevated_alerts": report["elevated_alerts"],
        "item_responses": item_responses,
    }
    cursor = conn.execute(
        """
        INSERT INTO psych_tests (
            crew_id, mission_stage, mood_score, stress_score, loneliness_score,
            motivation_score, wellbeing_index, recorded_at_utc, mood_state,
            sleep_onset_utc, wake_utc, assessment_type, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'BEHAVIORAL_MATRIX_20', ?)
        """,
        (
            crew_id,
            _mission_stage(conn),
            mood,
            stress,
            isolation,
            motivation,
            index,
            stamp,
            state_tag,
            sleep_onset_utc,
            wake_utc,
            json.dumps(payload),
        ),
    )
    alert_id: int | None = None
    total = report["total_load_score"]
    crosswalk = report["apa_crosswalk"]
    if total > 40:
        detail = "; ".join(report["elevated_alerts"]) or report["range_label"]
        alert_id = raise_wellbeing_alert(
            conn,
            crew_id,
            Severity.CRITICAL,
            "Behavioral Matrix: Critical Psychosocial Load",
            (
                f"Total psychosocial load {total}/80 ({report['readiness_status']}). "
                f"{detail}. Restrict critical duty and schedule clinical debrief."
            ),
            "wellbeing",
            stamp,
            category="PSYCHOSOCIAL",
        )
    elif total >= 21 or crosswalk["stage2_triggered"] or report["elevated_alerts"]:
        detail = "; ".join(report["elevated_alerts"]) or report["range_label"]
        alert_id = raise_wellbeing_alert(
            conn,
            crew_id,
            Severity.WARNING,
            "Behavioral Matrix: Elevated Psychosocial Load",
            (
                f"Psychosocial load {total}/80 ({report['readiness_status']}). "
                f"{detail}. Monitoring and crew rest advised."
            ),
            "wellbeing",
            stamp,
            category="PSYCHOSOCIAL",
        )
    return {
        "id": int(cursor.lastrowid),
        "wellbeing_index": index,
        "recorded_at_utc": stamp,
        "alert_id": alert_id,
        "matrix_report": payload,
    }


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
    ensure_mind_columns(conn)
    result = score_reaction_test(reaction_times_ms, false_starts)
    stamp = recorded_at_utc or _now()
    cursor = conn.execute(
        """
        INSERT INTO cognitive_tests (
            crew_id, mission_stage, test_type, reaction_ms, accuracy_pct, attention_score,
            duration_sec, recorded_at_utc, trials_total, valid_responses, false_starts, lapses,
            payload_json
        ) VALUES (?, ?, 'REACTION_ARENA', ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')
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


def _is_pilot(conn: sqlite3.Connection, crew_id: str) -> bool:
    row = conn.execute("SELECT role FROM crew_members WHERE id = ?", (crew_id,)).fetchone()
    return bool(row) and row["role"] == "PILOT"


def save_astrocow_session(
    conn: sqlite3.Connection,
    crew_id: str,
    data: dict[str, Any],
    *,
    recorded_at_utc: str | None = None,
) -> dict[str, Any]:
    ensure_mind_columns(conn)
    stamp = recorded_at_utc or _now()
    rt_samples = [float(x) for x in (data.get("reaction_times_ms") or []) if x is not None]
    rec_samples = [float(x) for x in (data.get("recovery_times_sec") or []) if x is not None]

    reticle_hits = int(data.get("reticle_hits") or 0)
    reticle_total = int(data.get("reticle_total") or 0)
    collisions = int(data.get("collisions") or 0)
    errors_after_change = int(data.get("errors_after_change") or 0)
    omitted = int(data.get("omitted_responses") or 0)
    duration_sec = max(1, int(data.get("duration_sec") or 1))
    score = int(data.get("score") or 0)
    high_score = max(score, int(data.get("high_score") or 0))
    difficulty_level = int(data.get("difficulty_level") or 1)

    if rt_samples:
        mean_rt = round(sum(rt_samples) / len(rt_samples), 1)
        if len(rt_samples) > 1:
            var = sum((x - mean_rt) ** 2 for x in rt_samples) / len(rt_samples)
            rt_var = round(math.sqrt(var), 1)
        else:
            rt_var = 0.0
    else:
        mean_rt = round(float(data.get("mean_reaction_ms") or 280.0), 1)
        rt_var = round(float(data.get("rt_variability_ms") or 0.0), 1)

    if rec_samples:
        recovery_sec = round(sum(rec_samples) / len(rec_samples), 2)
    elif data.get("recovery_time_sec") is not None:
        recovery_sec = round(float(data["recovery_time_sec"]), 2)
    else:
        recovery_sec = round(mean_rt / 1000.0, 2)

    if reticle_total > 0:
        precision_pct = round(100.0 * reticle_hits / reticle_total, 1)
    elif data.get("precision_pct") is not None:
        precision_pct = round(max(0.0, min(100.0, float(data["precision_pct"]))), 1)
    else:
        precision_pct = 100.0 if collisions == 0 else max(0.0, round(100.0 - collisions * 12.0, 1))

    raw_attn = precision_pct - errors_after_change * 4.0 - omitted * 5.0 - collisions * 3.0
    attention_score = round(max(0.0, min(100.0, raw_attn)), 1)
    pilot = _is_pilot(conn, crew_id)
    needs_obs = (
        mean_rt >= 380
        or recovery_sec >= 1.8
        or errors_after_change >= 3
        or omitted >= 2
        or precision_pct < 75
    )
    readiness = (
        "CRITICAL"
        if (mean_rt >= 600 or precision_pct < 55 or collisions >= 5)
        else "OBSERVATION"
        if needs_obs
        else "NOMINAL"
    )
    payload = {
        "test_type": "ASTROCOW_SIM",
        "score": score,
        "high_score": high_score,
        "difficulty_level": difficulty_level,
        "duration_sec": duration_sec,
        "mean_reaction_ms": mean_rt,
        "rt_variability_ms": rt_var,
        "recovery_time_sec": recovery_sec,
        "errors_after_change": errors_after_change,
        "omitted_responses": omitted,
        "precision_pct": precision_pct,
        "collisions": collisions,
        "reticle_hits": reticle_hits,
        "reticle_total": reticle_total,
        "focus_score": attention_score,
        "performance_by_minute": data.get("performance_by_minute") or [],
        "pilot_readiness": readiness,
    }
    cursor = conn.execute(
        """
        INSERT INTO cognitive_tests (
            crew_id, mission_stage, test_type, reaction_ms, accuracy_pct, attention_score,
            duration_sec, recorded_at_utc, trials_total, valid_responses, false_starts, lapses,
            payload_json
        ) VALUES (?, ?, 'ASTROCOW_SIM', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            crew_id,
            _mission_stage(conn),
            max(1.0, mean_rt),
            precision_pct,
            attention_score,
            duration_sec,
            stamp,
            reticle_total,
            reticle_hits,
            errors_after_change,
            omitted,
            json.dumps(payload),
        ),
    )
    alert_id: int | None = None
    if readiness != "NOMINAL":
        severe = (
            mean_rt >= 600
            or precision_pct < 55
            or collisions >= 5
            or (pilot and (mean_rt >= 450 or recovery_sec >= 2.2 or precision_pct < 70))
        )
        severity = Severity.CRITICAL if severe else Severity.WARNING
        msg = (
            f"AstroCow dual-task latency {mean_rt:g} ms (+/-{rt_var:g} ms), "
            f"T_recovery {recovery_sec:.2f} s, precision {precision_pct:.1f}%, "
            f"{errors_after_change} post-change errors."
        )
        if pilot:
            msg += " Critical impact on PILOT flight readiness."
        alert_id = raise_wellbeing_alert(
            conn,
            crew_id,
            severity,
            "AstroCow Sensorimotor Telemetry Below Target",
            msg,
            "alertness",
            stamp,
            category="SENSORIMOTOR",
        )
    return {
        "id": int(cursor.lastrowid),
        "recorded_at_utc": stamp,
        "alert_id": alert_id,
        "test_type": "ASTROCOW_SIM",
        "reaction_ms": mean_rt,
        "accuracy_pct": precision_pct,
        "attention_score": attention_score,
        "astrocow": payload,
    }


def save_neurofit_session(
    conn: sqlite3.Connection,
    crew_id: str,
    data: dict[str, Any],
    *,
    recorded_at_utc: str | None = None,
) -> dict[str, Any]:
    ensure_mind_columns(conn)
    stamp = recorded_at_utc or _now()
    stages = list(data.get("stages") or [])
    by_key = {str(s.get("key")): s for s in stages if isinstance(s, dict)}

    def _stage_acc(key: str, default: float = 0.0) -> float:
        st = by_key.get(key)
        if not st:
            return default
        total = int(st.get("total_attempts") or 0)
        hits = int(st.get("correct_attempts") or 0)
        if total > 0:
            return round(100.0 * hits / total, 1)
        return round(float(st.get("accuracy") or default), 1)

    retention_pct = _stage_acc("sequence", 0.0)
    attention_stroop = _stage_acc("bee", 0.0)
    spatial_reasoning_pct = _stage_acc("explorer", 0.0)
    visual_perception_pct = _stage_acc("scan", 0.0)
    sustained_attention_pct = round((attention_stroop + visual_perception_pct) / 2.0, 1)

    total_hits = sum(int(s.get("correct_attempts") or 0) for s in stages)
    total_errors = sum(int(s.get("error_attempts") or 0) for s in stages)
    total_attempts = sum(int(s.get("total_attempts") or 0) for s in stages)
    stage_dur = sum(int(s.get("duration_sec") or 0) for s in stages)
    duration_sec = max(1, int(data.get("duration_sec") or stage_dur or 1))
    total_score = int(data.get("total_score") or sum(int(s.get("score") or 0) for s in stages))

    acc_sum = retention_pct + attention_stroop + spatial_reasoning_pct + visual_perception_pct
    overall_accuracy = (
        round(100.0 * total_hits / total_attempts, 1)
        if total_attempts > 0
        else round(acc_sum / max(1, len(stages)), 1)
    )
    rt_vals = [
        float(s.get("avg_reaction_ms") or 0)
        for s in stages
        if float(s.get("avg_reaction_ms") or 0) > 0
    ]
    mean_rt = round(sum(rt_vals) / len(rt_vals), 1) if rt_vals else 0.0
    recovery_sec = round(mean_rt / 1000.0, 2) if mean_rt > 0 else 0.0

    raw_focus = (
        retention_pct * 0.30
        + sustained_attention_pct * 0.35
        + spatial_reasoning_pct * 0.20
        + visual_perception_pct * 0.15
    )
    rt_penalty = max(0.0, (mean_rt - 2500.0) / 250.0) if mean_rt > 2500.0 else 0.0
    focus_index = round(max(0.0, min(100.0, raw_focus - rt_penalty)), 1)

    ecg_index = int(data.get("ecg_index") or 400)
    payload = {
        "test_type": "NEUROFIT_LAB",
        "copilot_id": str(data.get("copilot_id") or "tamalito"),
        "ecg_index": ecg_index,
        "total_score": total_score,
        "duration_sec": duration_sec,
        "overall_accuracy_pct": overall_accuracy,
        "mean_reaction_ms": mean_rt,
        "recovery_time_sec": recovery_sec,
        "retention_pct": retention_pct,
        "sustained_attention_pct": sustained_attention_pct,
        "spatial_reasoning_pct": spatial_reasoning_pct,
        "visual_perception_pct": visual_perception_pct,
        "focus_index_score": focus_index,
        "total_hits": total_hits,
        "total_errors": total_errors,
        "total_attempts": total_attempts,
        "stages": stages,
        "cab_metrics": data.get("cab_metrics") or {},
        "diagnostic": data.get("diagnostic") or {},
    }
    cursor = conn.execute(
        """
        INSERT INTO cognitive_tests (
            crew_id, mission_stage, test_type, reaction_ms, accuracy_pct, attention_score,
            duration_sec, recorded_at_utc, trials_total, valid_responses, false_starts, lapses,
            payload_json
        ) VALUES (?, ?, 'NEUROFIT_LAB', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            crew_id,
            _mission_stage(conn),
            max(1.0, mean_rt),
            overall_accuracy,
            focus_index,
            duration_sec,
            stamp,
            total_attempts,
            total_hits,
            total_errors,
            json.dumps(payload),
        ),
    )
    alert_id: int | None = None
    pilot = _is_pilot(conn, crew_id)
    low_perf = (
        focus_index < 65
        or retention_pct < 60
        or sustained_attention_pct < 60
        or overall_accuracy < 65
    )
    if low_perf:
        severe = focus_index < 45 or (pilot and focus_index < 65)
        severity = Severity.CRITICAL if severe else Severity.WARNING
        msg = (
            f"NeuroFit Focus Index {focus_index:.1f}/100 (Retention {retention_pct:.1f}%, "
            f"Sustained Attention {sustained_attention_pct:.1f}%, Mean RT {mean_rt:g} ms)."
        )
        if pilot:
            msg += " Relevant to PILOT cognitive flight workload."
        alert_id = raise_wellbeing_alert(
            conn,
            crew_id,
            severity,
            "Cognitive Focus Battery Below Target",
            msg,
            "alertness",
            stamp,
            category="COGNITIVE",
        )
    return {
        "id": int(cursor.lastrowid),
        "recorded_at_utc": stamp,
        "alert_id": alert_id,
        "test_type": "NEUROFIT_LAB",
        "reaction_ms": mean_rt,
        "accuracy_pct": overall_accuracy,
        "attention_score": focus_index,
        "neurofit": payload,
    }


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


def _parse_json_dict(raw: str | None) -> dict[str, Any] | None:
    if not raw or raw == "{}":
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except (TypeError, ValueError):
        return None


def psych_profile(conn: sqlite3.Connection, crew_id: str, days: int | None = 14,
                  now: datetime | None = None) -> dict:
    """Read-only data for screen 05: latest state, mood trend and cognitive results.

    ``days`` sets the trend window (None = the whole mission).
    """
    now = now or datetime.now(UTC)
    newest = conn.execute(
        "SELECT MAX(recorded_at_utc) FROM psych_tests WHERE crew_id = ?", (crew_id,)
    ).fetchone()[0]
    newest_cog = conn.execute(
        "SELECT MAX(recorded_at_utc) FROM cognitive_tests WHERE crew_id = ?", (crew_id,)
    ).fetchone()[0]
    psych_now = min(now, parse_iso(newest)) if newest else now
    cog_candidates = [t for t in (newest, newest_cog) if t]
    cog_anchor = min(now, parse_iso(max(cog_candidates))) if cog_candidates else now
    since = (
        (psych_now - timedelta(days=days - 1)).strftime("%Y-%m-%dT00:00:00Z") if days else "0000"
    )
    cog_since = (
        (cog_anchor - timedelta(days=days - 1)).strftime("%Y-%m-%dT00:00:00Z") if days else "0000"
    )
    rows = conn.execute(
        """
        SELECT substr(recorded_at_utc, 1, 10) AS day,
               MAX(recorded_at_utc) AS last_at, mission_stage,
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
         "recorded_at_utc": r["last_at"], "mission_stage": r["mission_stage"],
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
        "SELECT * FROM cognitive_tests WHERE crew_id = ? AND test_type = 'REACTION_ARENA'"
        " ORDER BY recorded_at_utc DESC, id DESC LIMIT 1",
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

    psych_cols = {r["name"] for r in conn.execute("PRAGMA table_info(psych_tests)")}
    cog_cols = {r["name"] for r in conn.execute("PRAGMA table_info(cognitive_tests)")}

    behavioral_matrix = None
    if "assessment_type" in psych_cols and "payload_json" in psych_cols:
        matrix_row = conn.execute(
            "SELECT * FROM psych_tests"
            " WHERE crew_id = ? AND assessment_type = 'BEHAVIORAL_MATRIX_20'"
            " ORDER BY recorded_at_utc DESC, id DESC LIMIT 1",
            (crew_id,),
        ).fetchone()
        if matrix_row is not None:
            parsed = _parse_json_dict(matrix_row["payload_json"])
            if parsed is not None:
                behavioral_matrix = {**parsed, "recorded_at_utc": matrix_row["recorded_at_utc"]}

    astrocow = None
    astrocow_trend: list[dict[str, Any]] = []
    neurofit = None
    neurofit_trend: list[dict[str, Any]] = []
    if "payload_json" in cog_cols:
        astro_rows = conn.execute(
            "SELECT * FROM cognitive_tests WHERE crew_id = ? AND test_type = 'ASTROCOW_SIM'"
            " AND recorded_at_utc >= ? ORDER BY recorded_at_utc ASC, id ASC",
            (crew_id, cog_since),
        ).fetchall()
        for r in astro_rows:
            p = _parse_json_dict(r["payload_json"])
            if p is None:
                continue
            astrocow_trend.append(
                {
                    "day_label": day_label(mission_day(conn, parse_iso(r["recorded_at_utc"]))),
                    "recorded_at_utc": r["recorded_at_utc"],
                    "reaction_ms": p.get("mean_reaction_ms", r["reaction_ms"]),
                    "recovery_time_sec": p.get("recovery_time_sec", 0.0),
                    "precision_pct": p.get("precision_pct", r["accuracy_pct"]),
                    "focus_score": p.get("focus_score", r["attention_score"]),
                }
            )
        latest_astro = conn.execute(
            "SELECT * FROM cognitive_tests WHERE crew_id = ? AND test_type = 'ASTROCOW_SIM'"
            " ORDER BY recorded_at_utc DESC, id DESC LIMIT 1",
            (crew_id,),
        ).fetchone()
        if latest_astro is not None:
            p = _parse_json_dict(latest_astro["payload_json"])
            if p is not None:
                astrocow = {**p, "recorded_at_utc": latest_astro["recorded_at_utc"]}

        nf_rows = conn.execute(
            "SELECT * FROM cognitive_tests WHERE crew_id = ? AND test_type = 'NEUROFIT_LAB'"
            " AND recorded_at_utc >= ? ORDER BY recorded_at_utc ASC, id ASC",
            (crew_id, cog_since),
        ).fetchall()
        for r in nf_rows:
            p = _parse_json_dict(r["payload_json"])
            if p is None:
                continue
            neurofit_trend.append(
                {
                    "day_label": day_label(mission_day(conn, parse_iso(r["recorded_at_utc"]))),
                    "recorded_at_utc": r["recorded_at_utc"],
                    "focus_index_score": p.get("focus_index_score", r["attention_score"]),
                    "retention_pct": p.get("retention_pct", 0.0),
                    "sustained_attention_pct": p.get("sustained_attention_pct", 0.0),
                    "overall_accuracy_pct": p.get("overall_accuracy_pct", r["accuracy_pct"]),
                }
            )
        latest_nf = conn.execute(
            "SELECT * FROM cognitive_tests WHERE crew_id = ? AND test_type = 'NEUROFIT_LAB'"
            " ORDER BY recorded_at_utc DESC, id DESC LIMIT 1",
            (crew_id,),
        ).fetchone()
        if latest_nf is not None:
            p = _parse_json_dict(latest_nf["payload_json"])
            if p is not None:
                neurofit = {**p, "recorded_at_utc": latest_nf["recorded_at_utc"]}

    crew_info = conn.execute("SELECT role FROM crew_members WHERE id = ?", (crew_id,)).fetchone()
    daily_moods = [t["mood"] for t in trend]
    return {
        "crew_id": crew_id,
        "crew_role": crew_info["role"] if crew_info else "ASTRONAUT",
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
        "behavioral_matrix": behavioral_matrix,
        "astrocow": astrocow,
        "astrocow_trend": astrocow_trend,
        "neurofit": neurofit,
        "neurofit_trend": neurofit_trend,
    }
