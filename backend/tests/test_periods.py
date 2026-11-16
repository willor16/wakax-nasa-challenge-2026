"""Trend windows (24H · 7D · 14D · 30D · ALL) behind the interactive charts."""

from datetime import UTC, datetime

import pytest

from app.services.mission_clock import period_since


def test_period_since_counts_back_from_the_anchor():
    anchor = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    assert period_since(anchor, "24h") == "2026-11-14T12:00:00Z"
    assert period_since(anchor, "7d") == "2026-11-08T12:00:00Z"
    assert period_since(anchor, "all") is None


def test_mood_trend_follows_the_period(client, login):
    headers = login("ID-01")
    sizes = {}
    for period in ("7d", "14d", "30d", "all"):
        body = client.get(
            "/api/v1/psych/profile", headers=headers, params={"period": period}
        ).json()
        sizes[period] = len(body["trend"])
        for point in body["trend"]:
            assert point["recorded_at_utc"] and point["mission_stage"] in {
                "LAUNCH",
                "MISSION",
                "RETURN",
            }
    assert sizes["7d"] <= sizes["14d"] <= sizes["30d"] <= sizes["all"]
    assert sizes["7d"] <= 7 and sizes["14d"] <= 14


def test_vision_trend_points_carry_time_and_stage(client, login):
    body = client.get(
        "/api/v1/vision/ID-01", headers=login("ID-01"), params={"period": "all"}
    ).json()
    exams = [p for p in body["trend"] if p["kind"] == "EXAM"]
    assert exams and all(p["recorded_at_utc"] and p["mission_stage"] for p in exams)
    recent = client.get(
        "/api/v1/vision/ID-01", headers=login("ID-01"), params={"period": "30d"}
    ).json()
    assert len([p for p in recent["trend"] if p["kind"] == "EXAM"]) <= len(exams)


def test_cabin_co2_windows_are_bounded(client, login):
    headers = login("ID-02")
    day = client.get("/api/v1/auscultation/ID-02", headers=headers).json()["co2"]
    month = client.get(
        "/api/v1/auscultation/ID-02", headers=headers, params={"co2_period": "30d"}
    ).json()["co2"]
    assert day["period"] == "24h" and month["period"] == "30d"
    assert len(month["trend"]) <= 720
    times = [p["recorded_at_utc"] for p in month["trend"]]
    assert times == sorted(times)


def test_sleep_nights_carry_time_and_stage(client, login):
    body = client.get("/api/v1/sleep/ID-03", headers=login("ID-03"), params={"period": "7d"}).json()
    assert body["trend"]
    assert all(n["recorded_at_utc"] and n["mission_stage"] for n in body["trend"])


def test_measurements_filter_by_period_and_stage(client, login):
    headers = login("ID-01")
    everything = client.get(
        "/api/v1/measurements",
        headers=headers,
        params={"metric_key": "resting_hr_bpm", "limit": 200},
    ).json()
    week = client.get(
        "/api/v1/measurements",
        headers=headers,
        params={"metric_key": "resting_hr_bpm", "period": "7d", "limit": 200},
    ).json()
    launch = client.get(
        "/api/v1/measurements",
        headers=headers,
        params={"metric_key": "resting_hr_bpm", "stage": "LAUNCH", "limit": 200},
    ).json()
    assert 0 < len(week) < len(everything)
    assert launch and all(r["mission_stage"] == "LAUNCH" for r in launch)


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/v1/psych/profile", {"period": "90d"}),
        ("/api/v1/vision/ID-01", {"period": "7d"}),
        ("/api/v1/auscultation/ID-01", {"co2_period": "1y"}),
        ("/api/v1/measurements", {"period": "1h"}),
    ],
)
def test_unknown_windows_are_rejected(client, login, path, params):
    assert client.get(path, headers=login("ID-01"), params=params).status_code == 422
