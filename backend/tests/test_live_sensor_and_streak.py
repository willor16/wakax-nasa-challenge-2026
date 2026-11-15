"""Live wearable sensor (ECG + core temperature) and each crew member's own streak panel."""

import time

from app.services import live_sensor


def _frames(generator: live_sensor.LiveEcg, count: int) -> list[dict]:
    return [generator.frame() for _ in range(count)]


def test_frames_are_continuous_quarter_second_blocks():
    generator = live_sensor.LiveEcg(seed=1)
    generator.update(64, 55, 36.8)
    frames = _frames(generator, 8)
    assert all(len(f["samples"]) == 31 for f in frames)
    assert all(f["sample_rate_hz"] == 125 and f["lead"] == "II" for f in frames)
    starts = [f["t0_s"] for f in frames]
    assert starts == sorted(starts)
    assert abs((starts[1] - starts[0]) - 31 / 125) < 1e-6


def test_beats_follow_the_logged_heart_rate_and_temperature():
    generator = live_sensor.LiveEcg(seed=2)
    generator.update(72, 40, 36.9)
    frames = _frames(generator, 60)  # 15 s of signal
    late = frames[-1]
    assert abs(late["heart_rate_bpm"] - 72) <= 6
    assert all(abs(f["body_temp_c"] - 36.9) <= 0.031 for f in frames)
    peaks = sum(1 for f in frames for v in f["samples"] if v > 0.9)
    assert peaks > 0  # R waves are drawn
    generator.update(130, 10, 38.6)
    faster = _frames(generator, 40)[-1]
    assert faster["heart_rate_bpm"] >= 115
    assert faster["rhythm_text"] == "Sinus Tachycardia"


def test_injected_condition_applies_and_expires(monkeypatch):
    live_sensor.set_override("ID-01", heart_rate_bpm=130, body_temp_c=38.6, duration_s=60)
    assert live_sensor.active_override("ID-01").heart_rate_bpm == 130
    clock = time.monotonic() + 61
    monkeypatch.setattr(live_sensor.time, "monotonic", lambda: clock)
    assert live_sensor.active_override("ID-01") is None
    live_sensor.set_override("ID-01", body_temp_c=38.0, duration_s=600)
    live_sensor.clear_override("ID-01")
    assert live_sensor.active_override("ID-01") is None


def test_simulate_endpoint_respects_crew_access(client, login):
    own = client.post(
        "/api/v1/sensors/simulate", headers=login("ID-04"),
        json={"heart_rate_bpm": 125, "duration_s": 30},
    )
    assert own.status_code == 200 and own.json()["active"] is True
    other = client.post(
        "/api/v1/sensors/simulate", headers=login("ID-04"),
        json={"crew_id": "ID-01", "body_temp_c": 39},
    )
    assert other.status_code == 403
    physician = client.post(
        "/api/v1/sensors/simulate", headers=login("ID-03"),
        json={"crew_id": "ID-04", "clear": True},
    )
    assert physician.status_code == 200 and physician.json()["active"] is False
    empty = client.post("/api/v1/sensors/simulate", headers=login("ID-04"), json={})
    assert empty.status_code == 422


def test_sensor_inputs_follow_latest_reading_then_override(client, login, db):
    values, label = live_sensor.sensor_inputs(db, "ID-02")
    assert label is None and 30 < values["resting_hr_bpm"] < 120
    live_sensor.set_override("ID-02", heart_rate_bpm=140, duration_s=30, label_en="Tachycardia 140")
    values, label = live_sensor.sensor_inputs(db, "ID-02")
    assert values["resting_hr_bpm"] == 140 and "140" in label
    live_sensor.clear_override("ID-02")


def test_live_stream_needs_a_stream_token(client, login):
    assert client.get("/api/v1/stream/live-ecg", params={"token": "x" * 20}).status_code == 401


def test_live_stream_sends_unbuffered_ecg_frames(client, login, monkeypatch):
    from app.routers import system

    calls = {"n": 0}

    async def stop_after_two(request, started):
        calls["n"] += 1
        return calls["n"] <= 2

    monkeypatch.setattr(system, "_keep_streaming", stop_after_two)
    token = client.post("/api/v1/auth/stream-token", headers=login("ID-01")).json()["stream_token"]
    with client.stream("GET", "/api/v1/stream/live-ecg", params={"token": token}) as response:
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache, no-transform"
        assert response.headers["x-accel-buffering"] == "no"
        body = "".join(response.iter_text())
    assert body.count("event: ecg") == 2
    assert '"samples"' in body and '"body_temp_c"' in body


def test_public_streams_carry_anti_buffering_headers():
    from app.routers.system import SSE_HEADERS

    assert SSE_HEADERS["X-Accel-Buffering"] == "no"
    assert "no-transform" in SSE_HEADERS["Cache-Control"]


def test_personal_streak_is_private_and_complete(client, login):
    assert client.get("/api/v1/streaks/ID-01").status_code == 401
    assert client.get("/api/v1/streaks/ID-01", headers=login("ID-02")).status_code == 403
    body = client.get("/api/v1/streaks/ID-01", headers=login("ID-01")).json()
    assert body["crew"]["id"] == "ID-01"
    assert len(body["last_14_days"]) == 14
    assert [h["key"] for h in body["habits"]] == ["hydration", "nutrition", "exercise", "sleep"]
    assert all(h["target"] for h in body["habits"])
    assert body["best_streak_days"] >= body["active_streak_days"] >= 0
    assert body["rules"] == {"compliant_habits": 3, "shield_habits": 2}


def test_personal_streak_matches_public_board(client, login):
    mine = client.get("/api/v1/streaks/ID-03", headers=login("ID-03")).json()
    board = client.get("/api/v1/crew-streaks").json()
    public = next(c for c in board["crew"] if c["id"] == "ID-03")
    assert mine["active_streak_days"] == public["active_streak_days"]
    assert mine["best_streak_days"] == public["best_streak_days"]
    assert mine["last_14_days"][-7:] == public["last_7_days"]
