"""Sleep score and stage targets shared by capture, seed and the Sleep screen.

Targets come from the research references: 7-9 h asleep, deep (N3) 15-25%,
REM 20-25%, light (N1 + N2) 50-60%, efficiency 85% or more.
"""

from __future__ import annotations

from app.services.reference_ranges import sleep_reference

# Order of a typical night (17 bouts over 5 cycles): deep sleep is longest in the
# first half of the night and REM grows toward the morning.
NIGHT_PATTERN = (
    "AWAKE", "LIGHT", "DEEP", "LIGHT", "REM", "LIGHT", "DEEP", "AWAKE", "LIGHT",
    "REM", "LIGHT", "DEEP", "LIGHT", "REM", "AWAKE", "LIGHT", "REM",
)
_SHARES = {
    "DEEP": (0.45, 0.34, 0.21),
    "REM": (0.17, 0.26, 0.31, 0.26),
    "AWAKE": (0.33, 0.42, 0.25),
}


def _outside(value: float, low: float, high: float) -> float:
    if value < low:
        return low - value
    if value > high:
        return value - high
    return 0.0


def sleep_score(total_min: float, in_bed_min: float, deep_min: float, rem_min: float,
                awake_min: float) -> int:
    """0-100 score: duration, efficiency and stage balance against the references."""
    ref = sleep_reference()
    low, high = ref["total_min"]["nominal"]
    score = 100.0
    score -= _outside(total_min, low, high) / 4.0
    efficiency = total_min / in_bed_min * 100 if in_bed_min else 0
    score -= max(0.0, ref["efficiency_pct_min"] - efficiency) * 1.5
    if total_min > 0:
        score -= _outside(deep_min / total_min * 100, *ref["deep_pct"]) * 1.2
        score -= _outside(rem_min / total_min * 100, *ref["rem_pct"]) * 1.2
    score -= min(10.0, awake_min / 6.0)
    return int(max(0, min(100, round(score))))


def score_label(score: int, total_min: float | None = None) -> str:
    """OPTIMAL needs a good score and the 7 h minimum; a short night is FAIR at best."""
    short = total_min is not None and total_min < sleep_reference()["total_min"]["nominal"][0]
    if score >= 80 and not short:
        return "OPTIMAL"
    if score >= 65:
        return "FAIR"
    return "LOW"


def build_night(total_sleep_min: int, awake_min: int, deep_pct: float, rem_pct: float,
                jitter: list[float] | None = None) -> list[tuple[str, int]]:
    """Split a night into the 17-bout pattern as ``(stage, minutes)`` pairs."""
    deep_total = round(total_sleep_min * deep_pct / 100)
    rem_total = round(total_sleep_min * rem_pct / 100)
    light_total = total_sleep_min - deep_total - rem_total
    light_count = NIGHT_PATTERN.count("LIGHT")
    jitter = jitter or [0.0] * light_count
    light_weights = [max(0.4, 1.0 + j) for j in jitter[:light_count]]
    light_parts = [light_total * w / sum(light_weights) for w in light_weights]

    totals = {"DEEP": deep_total, "REM": rem_total, "AWAKE": awake_min}
    counters = {"DEEP": 0, "REM": 0, "AWAKE": 0, "LIGHT": 0}
    bouts: list[tuple[str, int]] = []
    for stage in NIGHT_PATTERN:
        index = counters[stage]
        counters[stage] += 1
        if stage == "LIGHT":
            minutes = light_parts[index]
        else:
            minutes = totals[stage] * _SHARES[stage][index]
        bouts.append((stage, max(1, round(minutes))))
    return bouts
