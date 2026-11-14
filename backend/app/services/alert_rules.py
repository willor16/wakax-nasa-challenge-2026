"""Pure alert decision rules (D3-01). No database access and no I/O.

The functions here decide *whether* a single reading deserves an alert, how
severe it is and whether it may wait until Quiet Hours end. Wiring to SQLite
(reading ``metric_catalog`` / ``baselines`` and inserting ``alerts`` rows) is
done by ``app.services.contracts.evaluate_alerts``.

Rules:
* Fixed limits come from ``metric_catalog`` (nominal / warning / critical).
* Personal drift is a z-score against the crew member's own ``baselines`` row.
* The final severity is the highest of both checks.
* Non-critical alerts raised during Quiet Hours are deferred; CRITICAL never is.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
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


def z_score(value: float, baseline: Baseline | None) -> float | None:
    """Distance from the personal mean in standard deviations, if it is meaningful."""
    if baseline is None or baseline.sample_count < MIN_BASELINE_SAMPLES:
        return None
    if baseline.std_dev <= 0:
        return None
    return (value - baseline.mean_val) / baseline.std_dev


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
    """Parse an ISO-8601 UTC timestamp such as ``2026-11-14T23:30:00Z``."""
    return datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))


def decide(
    value: float,
    limits: MetricThresholds,
    baseline: Baseline | None,
    recorded_at_utc: str,
    quiet: QuietHours | None = None,
) -> AlertDecision | None:
    """Evaluate one reading. Returns None when no alert is needed."""
    fixed = classify_value(value, limits)
    z = z_score(value, baseline)
    drift = classify_z(z)
    candidates = [s for s in (fixed, drift) if s is not None]
    if not candidates:
        return None
    severity = max(candidates)
    if fixed is not None:
        is_above = value > limits.nominal_max
    else:
        is_above = z is not None and z > 0
    return AlertDecision(
        severity=severity,
        is_above=is_above,
        z=z,
        is_quiet_deferred=should_defer(severity, parse_utc(recorded_at_utc), quiet),
    )


def build_alert_texts(display_name: str, unit: str, value: float, decision: AlertDecision,
                      limits: MetricThresholds) -> tuple[str, str]:
    """Plain-language title and message for the crew (no clinical jargon)."""
    direction = "higher" if decision.is_above else "lower"
    title = f"{display_name} is {direction} than expected"
    message = (
        f"Your reading was {value:g} {unit}. The usual range is "
        f"{limits.nominal_min:g} to {limits.nominal_max:g} {unit}."
    )
    if decision.severity is Severity.CRITICAL:
        message += " Please follow the guide steps now and tell the crew physician."
    elif decision.is_quiet_deferred:
        message += " This can wait until the rest period ends."
    return title, message
