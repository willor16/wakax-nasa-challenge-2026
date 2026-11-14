"""Unit tests for the pure alert rules (D3-01)."""

from datetime import UTC, datetime

import pytest

from app.services.alert_rules import (
    Baseline,
    MetricThresholds,
    QuietHours,
    Severity,
    build_alert_texts,
    classify_value,
    classify_z,
    decide,
    is_quiet_hours,
    should_defer,
    z_score,
)

# Mirrors resting_hr_bpm in the seed snapshot.
HR = MetricThresholds(
    nominal_min=50, nominal_max=85, warning_min=45, warning_max=95,
    critical_min=40, critical_threshold=110,
)
# Mirrors cabin_co2_ppm: one-sided limits.
CO2 = MetricThresholds(
    nominal_min=350, nominal_max=2000, warning_max=3000, critical_threshold=4000,
)
BASE = Baseline(mean_val=60, std_dev=5, sample_count=10)
DAY = "2026-11-14T14:00:00Z"
NIGHT = "2026-11-14T23:30:00Z"


def at(hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(2026, 11, 14, int(h), int(m), tzinfo=UTC)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (60, None),
        (50, None),
        (85, None),
        (86, Severity.INFO),
        (49, Severity.INFO),
        (95, Severity.INFO),
        (96, Severity.WARNING),
        (44, Severity.WARNING),
        (40, Severity.WARNING),
        (39.9, Severity.CRITICAL),
        (110, Severity.CRITICAL),
    ],
)
def test_classify_value_boundaries(value: float, expected: Severity | None) -> None:
    assert classify_value(value, HR) is expected


def test_classify_value_with_missing_limits() -> None:
    assert classify_value(1000, CO2) is None
    assert classify_value(2500, CO2) is Severity.INFO
    assert classify_value(3500, CO2) is Severity.WARNING
    assert classify_value(4000, CO2) is Severity.CRITICAL
    assert classify_value(100, CO2) is Severity.INFO  # below nominal, no lower warning bound


def test_z_score_needs_valid_baseline() -> None:
    assert z_score(70, BASE) == pytest.approx(2.0)
    assert z_score(70, None) is None
    assert z_score(70, Baseline(60, 0, 10)) is None
    assert z_score(70, Baseline(60, 5, 2)) is None


@pytest.mark.parametrize(
    ("z", "expected"),
    [(None, None), (0.5, None), (1.99, None), (2.0, Severity.INFO),
     (-2.5, Severity.INFO), (3.0, Severity.WARNING), (-7.0, Severity.WARNING)],
)
def test_classify_z(z: float | None, expected: Severity | None) -> None:
    assert classify_z(z) is expected


def test_quiet_hours_wrap_midnight() -> None:
    assert is_quiet_hours(at("22:00")) is True
    assert is_quiet_hours(at("23:59")) is True
    assert is_quiet_hours(at("00:00")) is True
    assert is_quiet_hours(at("05:59")) is True
    assert is_quiet_hours(at("06:00")) is False
    assert is_quiet_hours(at("21:59")) is False
    assert is_quiet_hours(at("14:00")) is False


def test_quiet_hours_same_day_window_and_disabled() -> None:
    nap = QuietHours("13:00", "15:00")
    assert is_quiet_hours(at("14:00"), nap) is True
    assert is_quiet_hours(at("15:00"), nap) is False
    assert is_quiet_hours(at("23:00"), QuietHours("00:00", "00:00")) is False


@pytest.mark.parametrize("hhmm", ["23:30", "03:00", "14:00"])
def test_critical_is_never_deferred(hhmm: str) -> None:
    assert should_defer(Severity.CRITICAL, at(hhmm)) is False


def test_non_critical_deferred_only_at_night() -> None:
    assert should_defer(Severity.WARNING, at("23:30")) is True
    assert should_defer(Severity.INFO, at("02:00")) is True
    assert should_defer(Severity.WARNING, at("14:00")) is False


def test_decide_nominal_reading_returns_none() -> None:
    assert decide(61, HR, BASE, DAY) is None


def test_decide_takes_highest_of_fixed_and_drift() -> None:
    # 80 bpm is nominal but 4 SD above this person's mean -> WARNING from drift.
    result = decide(80, HR, BASE, DAY)
    assert result is not None
    assert result.severity is Severity.WARNING
    assert result.is_above is True
    assert result.z == pytest.approx(4.0)


def test_decide_critical_at_night_is_not_deferred() -> None:
    result = decide(120, HR, BASE, NIGHT)
    assert result is not None
    assert result.severity is Severity.CRITICAL
    assert result.is_quiet_deferred is False


def test_decide_warning_at_night_is_deferred() -> None:
    result = decide(98, HR, None, NIGHT)
    assert result is not None
    assert result.severity is Severity.WARNING
    assert result.is_quiet_deferred is True


def test_decide_uses_mission_quiet_hours() -> None:
    result = decide(98, HR, None, NIGHT, QuietHours("01:00", "05:00"))
    assert result is not None
    assert result.is_quiet_deferred is False


def test_alert_texts_are_plain_english() -> None:
    result = decide(120, HR, None, DAY)
    assert result is not None
    title, message = build_alert_texts("Resting Heart Rate", "bpm", 120, result, HR)
    assert title == "Resting Heart Rate is higher than expected"
    assert "120 bpm" in message
    assert "crew physician" in message
    for jargon in ("z-score", "threshold", "baseline", "SD"):
        assert jargon not in title + message
