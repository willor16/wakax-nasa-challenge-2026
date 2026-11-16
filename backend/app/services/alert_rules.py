"""Pure alert decision rules (D3-01). No database access and no I/O.

The functions here decide *whether* a single reading deserves an alert, how
severe it is and whether it may wait until Quiet Hours end. Wiring to SQLite
(reading ``metric_catalog`` / ``baselines`` and inserting ``alerts`` rows) is
done by ``app.services.alert_engine``, called from
``app.services.contracts.evaluate_alerts``.

Rules:
* Fixed limits come from ``metric_catalog`` (nominal / warning / critical).
* Personal drift is a z-score against the crew member's own ``baselines`` row.
* The final severity is the highest of both checks. Drift alone stays INFO
  while the value is still inside the usual (nominal) range.
* Role focus: metrics that define fitness for a crew member's role (vision for a
  PILOT, heart and lungs for an OPERATOR) are raised from INFO to WARNING.
* Non-critical alerts raised during Quiet Hours are deferred; CRITICAL never is.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from enum import IntEnum

DEFAULT_QUIET_START = "22:00"
DEFAULT_QUIET_END = "06:00"

# z-score limits for personal drift (absolute value), following statistical
# process control: 2 SD "warning limits" and 3 SD "action limits".
# References: Shewhart W.A., Economic Control of Quality of Manufactured Product
# (1931); Westgard J.O. et al., "A multi-rule Shewhart chart for quality control
# in clinical chemistry", Clinical Chemistry 27(3):493-501 (1981), rules 1-2s/1-3s.
# A minimum of 3 baseline samples is required before drift is trusted.
Z_INFO = 2.0
Z_WARNING = 3.0
MIN_BASELINE_SAMPLES = 3

# Requirements spec section 2 and RNF 2: a PILOT is cleared on vision and
# reaction, an OPERATOR (spacewalks) on heart, lungs and recovery after effort.
ROLE_FOCUS_METRICS: dict[str, frozenset[str]] = {
    "PILOT": frozenset({
        "optic_sheath_left_mm", "optic_sheath_right_mm", "iop_left_mmhg", "iop_right_mmhg",
    }),
    "OPERATOR": frozenset({
        "resting_hr_bpm", "hrv_rmssd_ms", "bp_systolic_mmhg", "spo2_pct", "vo2_max_ml_kg_min",
    }),
}
ROLE_LABELS = {"PILOT": "piloting", "OPERATOR": "spacewalk duty"}


class Severity(IntEnum):
    """Ordered severity levels; names match ``alerts.severity`` CHECK values."""

    INFO = 1
    WARNING = 2
    CRITICAL = 3


@dataclass(frozen=True, slots=True)
class MetricThresholds:
    """Limits for one metric, mirroring a ``metric_catalog`` row."""

    nominal_min: float
    nominal_max: float
    warning_min: float | None = None
    warning_max: float | None = None
    critical_min: float | None = None
    critical_threshold: float | None = None


@dataclass(frozen=True, slots=True)
class Baseline:
    """Personal reference for one metric, mirroring a ``baselines`` row."""

    mean_val: float
    std_dev: float
    sample_count: int


@dataclass(frozen=True, slots=True)
class QuietHours:
    """Quiet window in UTC as ``HH:MM``; it may wrap past midnight."""

    start_utc: str = DEFAULT_QUIET_START
    end_utc: str = DEFAULT_QUIET_END


@dataclass(frozen=True, slots=True)
class AlertDecision:
    """Outcome of evaluating one reading."""

    severity: Severity
    is_above: bool
    z: float | None
    is_quiet_deferred: bool
    role_focus: bool = False


def classify_value(value: float, limits: MetricThresholds) -> Severity | None:
    """Return the severity from fixed limits, or None when the value is nominal."""
    if limits.critical_threshold is not None and value >= limits.critical_threshold:
        return Severity.CRITICAL
    if limits.critical_min is not None and value < limits.critical_min:
        return Severity.CRITICAL
    if limits.warning_max is not None and value > limits.warning_max:
        return Severity.WARNING
    if limits.warning_min is not None and value < limits.warning_min:
        return Severity.WARNING
    if value > limits.nominal_max or value < limits.nominal_min:
        return Severity.INFO
    return None


def z_score(value: float, baseline: Baseline | None, sd_floor: float = 0.0) -> float | None:
    """Distance from the personal mean in standard deviations, if it is meaningful.

    ``sd_floor`` is the repeatability of the measurement itself: a short
    pre-flight series can show a spread smaller than the instrument can
    resolve, which would turn ordinary readings into false drift.
    """
    if baseline is None or baseline.sample_count < MIN_BASELINE_SAMPLES:
        return None
    spread = max(baseline.std_dev, sd_floor)
    if spread <= 0:
        return None
    return (value - baseline.mean_val) / spread


def classify_z(z: float | None) -> Severity | None:
    """Map personal drift to a severity. Drift alone never reaches CRITICAL."""
    if z is None:
        return None
    if abs(z) >= Z_WARNING:
        return Severity.WARNING
    if abs(z) >= Z_INFO:
        return Severity.INFO
    return None


def _parse_hhmm(text: str) -> time:
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))


def is_quiet_hours(moment_utc: datetime, quiet: QuietHours | None = None) -> bool:
    """True when ``moment_utc`` falls inside the quiet window (start inclusive)."""
    quiet = quiet or QuietHours()
    start = _parse_hhmm(quiet.start_utc)
    end = _parse_hhmm(quiet.end_utc)
    now = moment_utc.time().replace(second=0, microsecond=0)
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def should_defer(severity: Severity, moment_utc: datetime, quiet: QuietHours | None = None) -> bool:
    """Defer non-critical alerts during Quiet Hours. CRITICAL is always immediate."""
    if severity is Severity.CRITICAL:
        return False
    return is_quiet_hours(moment_utc, quiet)


def parse_utc(timestamp_utc: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp such as ``2026-11-14T23:30:00Z``.

    Timestamps without an offset are taken as UTC so they never mix with aware ones.
    """
    parsed = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def is_role_focus(role: str | None, metric_key: str) -> bool:
    """True when the metric is part of the fitness check for this crew role."""
    return metric_key in ROLE_FOCUS_METRICS.get(role or "", frozenset())


def decide(
    value: float,
    limits: MetricThresholds,
    baseline: Baseline | None,
    recorded_at_utc: str,
    quiet: QuietHours | None = None,
    role_focus: bool = False,
    drift_direction: str = "both",
    sd_floor: float = 0.0,
) -> AlertDecision | None:
    """Evaluate one reading. Returns None when no alert is needed.

    ``role_focus`` raises an out-of-range INFO result to WARNING; it never
    creates an alert on its own and never reaches CRITICAL. ``drift_direction``
    is ``both``, ``up``, ``down`` or ``none`` (which side of the personal
    baseline matters for this metric).
    """
    fixed = classify_value(value, limits)
    z = None if drift_direction == "none" else z_score(value, baseline, sd_floor)
    if z is not None and ((drift_direction == "up" and z < 0)
                          or (drift_direction == "down" and z > 0)):
        z = None  # movement in the harmless direction is not a finding
    drift = classify_z(z)
    if fixed is None and drift is not None:
        # Inside the usual range a personal drift is a trend to watch, not a
        # warning: it informs without changing the crew member's readiness.
        drift = Severity.INFO
    candidates = [s for s in (fixed, drift) if s is not None]
    if not candidates:
        return None
    severity = max(candidates)
    # Role focus only raises readings that already left the usual range.
    raised = role_focus and severity is Severity.INFO and fixed is Severity.INFO
    if raised:
        severity = Severity.WARNING
    if fixed is not None:
        is_above = value > limits.nominal_max
    else:
        is_above = z is not None and z > 0
    return AlertDecision(
        severity=severity,
        is_above=is_above,
        z=z,
        is_quiet_deferred=should_defer(severity, parse_utc(recorded_at_utc), quiet),
        # The role note is shown on every WARNING of a role-defining metric.
        role_focus=role_focus and severity is Severity.WARNING,
    )


TREND_READINGS = 3


TREND_MIN_CHANGE = 2.0  # times the measurement repeatability
TREND_MIN_Z = 1.0


def adverse_trend(values: list[float], direction: str, floor: float = 0.0,
                  baseline: Baseline | None = None) -> str | None:
    """``"up"`` or ``"down"`` when the last readings (oldest first) move steadily in the
    one harmful direction of the metric (optic nerve sheath rising, heart rate variability
    falling): every step the same way, the whole change at least twice the measurement
    repeatability, and the newest reading already away from the personal baseline on that
    side. Day-to-day wobble is never read as a trend. None otherwise.
    """
    if direction not in ("up", "down") or len(values) < TREND_READINGS:
        return None
    last = values[-TREND_READINGS:]
    steps = [b - a for a, b in zip(last, last[1:], strict=False)]
    change = last[-1] - last[0]
    if abs(change) < max(TREND_MIN_CHANGE * floor, 1e-9):
        return None
    way = "up" if all(d > 0 for d in steps) else "down" if all(d < 0 for d in steps) else None
    if way != direction:
        return None
    if baseline is not None:
        z = z_score(last[-1], baseline, floor)
        if z is None or (z if way == "up" else -z) < TREND_MIN_Z:
            return None
    return way


def format_amount(value: float, unit: str) -> str:
    """``5.9 mm``, ``98%`` - numbers rounded for reading, never scientific notation."""
    text = f"{round(value, 2):g}"
    return f"{text}{unit}" if unit == "%" else f"{text} {unit}"


_QUALIFIERS = {
    Severity.INFO: ("slightly elevated", "slightly low"),
    Severity.WARNING: ("elevated", "low"),
    Severity.CRITICAL: ("well above the safe limit", "well below the safe limit"),
}


def build_alert_texts(
    display_name: str,
    unit: str,
    value: float,
    decision: AlertDecision,
    limits: MetricThresholds,
    baseline_mean: float | None = None,
    role: str | None = None,
) -> tuple[str, str]:
    """Plain-language title and message, in the style of the Notifications screen.

    Example: ``Right Optic Nerve Sheath Diameter elevated (5.9 mm)`` /
    ``Above personal baseline (4.3 mm). Review preventive care on the right.``
    """
    above, below = _QUALIFIERS[decision.severity]
    title = f"{display_name} {above if decision.is_above else below} ({format_amount(value, unit)})"

    side = "Above" if decision.is_above else "Below"
    if baseline_mean is not None and decision.z is not None:
        message = f"{side} personal baseline ({format_amount(baseline_mean, unit)})."
    else:
        low, high = format_amount(limits.nominal_min, unit), format_amount(limits.nominal_max, unit)
        message = f"{side} the usual range ({low} to {high})."
    if decision.role_focus and role in ROLE_LABELS:
        message += f" Important for {ROLE_LABELS[role]}."
    if decision.severity is Severity.CRITICAL:
        message += " Follow the care steps now and call the crew physician."
    elif decision.is_quiet_deferred:
        message += " This can wait until the rest period ends."
    else:
        message += " Review preventive care on the right."
    return title, message
