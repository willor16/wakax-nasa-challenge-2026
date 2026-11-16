"""Capture -> results flow for the clinical modules, and the no-invented-values rule."""

import hashlib
import json
from datetime import timedelta

import pytest

from app.services import acoustics
from app.services.mission_clock import to_iso, utc_now


def _post(client, headers, items, **extra):
    return client.post("/api/v1/measurements", headers=headers, json={"items": items, **extra})


def _new_crew(client, login, crew_id="ID-05"):
    """A crew member with no readings at all."""
    client.post(
        "/api/v1/crew",
        headers=login("ID-02"),
        json={
            "id": crew_id,
            "code": crew_id.replace("-", "·"),
            "full_name": "Nova Reyes",
            "role": "ASTRONAUT",
            "pin": "5555",
            "age": 30,
            "sex": "F",
            "height_cm": 165,
        },
    )
    token = client.post("/api/v1/auth/login", json={"crew_id": crew_id, "pin": "5555"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


# ---------------------------------------------------------------- ingestion ---


def test_ingestion_validates_and_files_under_the_mission_stage(client, login):
    me = login("ID-03")
    saved = _post(client, me, [{"metric_key": "resting_hr_bpm", "value_num": 62}])
    assert saved.status_code == 201
    body = saved.json()
    assert body["mission_stage"] == "MISSION" and body["alerts_created"] == []
    assert (
        _post(client, me, [{"metric_key": "resting_hr_bpm", "value_num": 5000}]).status_code == 422
    )
    assert _post(client, me, [{"metric_key": "not_a_metric", "value_num": 1}]).status_code == 422
    # Pre-flight baselines cannot be rewritten once the mission is under way.
    rewrite = _post(
        client, me, [{"metric_key": "resting_hr_bpm", "value_num": 90}], mission_stage="LAUNCH"
    )
    assert rewrite.status_code == 422
    future = _post(
        client,
        me,
        [{"metric_key": "resting_hr_bpm", "value_num": 62}],
        recorded_at_utc=to_iso(utc_now() + timedelta(hours=2)),
    )
    assert future.status_code == 422
    # Nobody can log readings for somebody else, except the physician.
    assert (
        _post(
            client,
            login("ID-01"),
            [{"metric_key": "resting_hr_bpm", "value_num": 62}],
            crew_id="ID-04",
        ).status_code
        == 403
    )
    assert (
        _post(
            client, me, [{"metric_key": "resting_hr_bpm", "value_num": 82}], crew_id="ID-04"
        ).status_code
        == 201
    )


def test_out_of_range_reading_raises_an_alert_with_care_steps(client, login):
    me = login("ID-03")
    saved = _post(client, me, [{"metric_key": "spo2_pct", "value_num": 90}])
    assert len(saved.json()["alerts_created"]) == 1
    alerts = client.get("/api/v1/alerts", headers=me).json()
    top = alerts["items"][0]
    assert top["severity"] == "CRITICAL" and "Blood Oxygen" in top["title_en"]
    assert len(top["care_steps"]) == 3 and top["guide_article_id"]
    assert alerts["counts"]["urgent"] == 1
    assert client.get("/api/v1/mission").json()["cabin_mode"] == "critical"  # vital emergency
    # A repeat reading minutes later does not stack a second copy.
    again = _post(client, me, [{"metric_key": "spo2_pct", "value_num": 90}])
    assert again.json()["alerts_created"] == []
    done = client.post(f"/api/v1/alerts/{top['id']}/steps/0/complete", headers=me).json()
    assert done["care_steps"][0]["done_at_utc"]
    assert client.post(f"/api/v1/alerts/{top['id']}/acknowledge", headers=me).status_code == 200
    assert client.get("/api/v1/alerts", headers=me).json()["counts"]["advisories"] == 0


def test_hydration_reminder_uses_the_personal_goal(client, login):
    me = _new_crew(client, login)
    first = _post(client, me, [{"metric_key": "hydration_ml", "value_num": 400}])
    assert len(first.json()["alerts_created"]) == 1
    alert = client.get("/api/v1/alerts", headers=me).json()["items"][0]
    assert "remaining to complete daily hydration goal" in alert["title_en"]
    assert alert["severity"] == "WARNING"
    # More water the same day does not repeat the reminder; reaching the goal is silent.
    rest = _post(client, me, [{"metric_key": "hydration_ml", "value_num": 2000}])
    assert rest.json()["alerts_created"] == []


# ------------------------------------------------------------- no invention ---


def test_profile_without_readings_shows_no_data_never_defaults(client, login):
    me = _new_crew(client, login)
    profile = client.get("/api/v1/crew/ID-05/profile", headers=me).json()
    assert all(card["value"] is None for card in profile["biometrics"])
    assert all(card["status"] == "NO_DATA" for card in profile["biometrics"])
    assert profile["ecg"] is None
    assert profile["scan"]["core_temp"]["value"] is None and profile["scan"]["hydration_ml"] is None
    assert all(row["value"] is None for row in profile["daily"])
    assert profile["on_target"] == 0
    assert all(
        lab.get("value") is None and lab.get("value_text") is None for lab in profile["labs"]
    )
    assert profile["work"]["interior_min"] is None

    sleep = client.get("/api/v1/sleep/ID-05", headers=me).json()
    assert sleep["summary"] is None and sleep["night"] is None and sleep["nights"] == 0
    vision = client.get("/api/v1/vision/ID-05", headers=me).json()
    assert vision["status"] == "NO_DATA" and vision["review"]["state"] == "NO_EXAM"
    assert vision["eyes"]["left"]["value"] is None and vision["trend"] == []
    sounds = client.get("/api/v1/auscultation/ID-05", headers=me).json()
    assert sounds["cardiac"] is None and sounds["pulmonary"] is None
    assert sounds["status"] == "NO_DATA"
    mind = client.get("/api/v1/psych/profile", headers=me).json()
    assert mind["scales"] is None and mind["reaction"] is None and mind["trend"] == []


def test_reads_never_write(client, login, db):
    def counts():
        return [
            db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in (
                "measurements",
                "sleep_sessions",
                "sleep_stages",
                "streak_days",
                "alerts",
                "diagnoses",
            )
        ]

    before = counts()
    me = login("ID-01")
    for path in (
        "/api/v1/crew/ID-01/profile",
        "/api/v1/sleep/ID-01?period=30d",
        "/api/v1/vision/ID-01",
        "/api/v1/auscultation/ID-01",
        "/api/v1/psych/profile",
        "/api/v1/crew-overview",
        "/api/v1/crew-streaks",
    ):
        assert client.get(path, headers=me).status_code == 200
    assert counts() == before


# ------------------------------------------------------------------ profile ---


def test_profile_reflects_stored_readings_and_reference_status(client, login):
    me = login("ID-01")
    profile = client.get("/api/v1/crew/ID-01/profile", headers=me).json()
    assert (
        profile["crew"]["full_name"] == "Elena Vargas"
        and profile["crew"]["title_en"] == "Commander"
    )
    cards = {c["metric_key"]: c for c in profile["biometrics"]}
    assert cards["body_weight_kg"]["value"] == 63.8
    assert cards["bmi_kg_m2"]["value"] == pytest.approx(63.8 / 1.732**2, abs=0.1)
    assert cards["bmi_kg_m2"]["status"] == "NOMINAL"
    assert 95 < cards["muscle_mass_kg"]["baseline_pct"] < 100
    assert cards["height_cm"]["stages"]["LAUNCH"] == pytest.approx(171, abs=0.5)
    assert cards["height_cm"]["stages"]["RETURN"] is None
    daily = {r["metric_key"]: r for r in profile["daily"]}
    assert daily["resting_hr_bpm"]["value"] == 64 and daily["resting_hr_bpm"]["status"] == "NOMINAL"
    assert (
        daily["blood_pressure"]["value"] == 118 and daily["blood_pressure"]["value_secondary"] == 76
    )
    assert (
        daily["hydration_ml"]["status"] == "WARNING"
        and "Low" in daily["hydration_ml"]["status_text"]
    )
    assert profile["ecg"]["rhythm_text"] == "Normal Sinus"
    assert abs(profile["ecg"]["heart_rate_bpm"] - 64) <= 3  # measured from the stored strip
    labs = {lab["metric_key"]: lab for lab in profile["labs"]}
    assert labs["blood_glucose_mg_dl"]["value"] == 89
    assert labs["auscultation_vision"]["status"] == "CRITICAL"
    assert "5.9 mm" in labs["auscultation_vision"]["note"]
    assert profile["environment"]["co2_mmhg"] == pytest.approx(2.8, abs=0.5)

    _post(client, me, [{"metric_key": "body_temp_c", "value_num": 38.6}])
    fever = client.get("/api/v1/crew/ID-01/profile", headers=me).json()
    assert fever["scan"]["core_temp"]["status"] == "CRITICAL"


# -------------------------------------------------------------------- sleep ---


def test_sleep_monitor_last_night_and_periods(client, login):
    me = login("ID-01")
    night = client.get("/api/v1/sleep/ID-01", headers=me).json()
    summary = night["summary"]
    assert summary["total_min"] == pytest.approx(432, abs=6) and summary["target_met"]
    assert summary["score"] >= 80 and summary["score_label"] == "OPTIMAL"
    stages = {s["stage"]: s for s in night["stages"]}
    assert stages["DEEP"]["target_low_pct"] == 15 and stages["REM"]["target_high_pct"] == 25
    assert sum(b["minutes"] for b in night["night"]["bouts"]) == summary["in_bed_min"]
    assert night["night"]["bout_count"] == 17
    month = client.get("/api/v1/sleep/ID-01?period=30d", headers=me).json()
    assert month["nights"] == 30 and len(month["trend"]) == 30
    short = client.get("/api/v1/sleep/ID-02", headers=login("ID-02")).json()["summary"]
    assert short["total_min"] < 360 and not short["target_met"]
    assert short["score_label"] != "OPTIMAL"  # a short night is never rated optimal
    assert client.get("/api/v1/sleep/ID-01?period=2d", headers=me).status_code == 422


def test_sleep_capture_from_the_check_in_feeds_the_sleep_screen(client, login, monkeypatch):
    me = _new_crew(client, login)
    saved = client.post(
        "/api/v1/psych/checkins",
        headers=me,
        json={
            "mood_state": "CALM",
            "mood": 4,
            "stress": 2,
            "isolation": 1,
            "motivation": 5,
            "sleep_onset_utc": "22:30",
            "wake_utc": "06:00",
        },
    )
    assert saved.status_code == 201
    if saved.json()["sleep_session"] is None:
        pytest.skip("06:00 UTC today has not happened yet for a brand-new profile")
    assert saved.json()["sleep_session"]["time_in_bed_min"] == 450
    sleep = client.get("/api/v1/sleep/ID-05", headers=me).json()
    assert sleep["summary"]["window_start"] == "22:30" and sleep["summary"]["window_end"] == "06:00"
    # Without the sleep band only the window is known: no stage breakdown is made up.
    assert sleep["summary"]["stages_recorded"] is False and sleep["stages"] == []
    assert sleep["night"] is None
    again = client.post(
        "/api/v1/psych/checkins",
        headers=me,
        json={
            "mood": 4,
            "stress": 2,
            "isolation": 1,
            "motivation": 5,
            "sleep_onset_utc": "22:30",
            "wake_utc": "06:00",
        },
    ).json()
    assert again["sleep_session"] is None and "already logged" in again["sleep_note_en"]


def test_sleep_session_rules(client, login):
    me = login("ID-03")
    now = utc_now()
    bad = client.post(
        "/api/v1/sleep/sessions",
        headers=me,
        json={
            "sleep_start_utc": to_iso(now - timedelta(hours=1)),
            "sleep_end_utc": to_iso(now - timedelta(hours=2)),
        },
    )
    assert bad.status_code == 422 and "after sleep onset" in bad.json()["detail"]
    stages = [
        {"stage": "LIGHT", "duration_min": 100},
        {"stage": "DEEP", "duration_min": 50},
        {"stage": "REM", "duration_min": 40},
        {"stage": "AWAKE", "duration_min": 10},
    ]
    nap = client.post(
        "/api/v1/sleep/sessions",
        headers=me,
        json={
            "sleep_start_utc": to_iso(now - timedelta(minutes=215)),
            "sleep_end_utc": to_iso(now - timedelta(minutes=15)),
            "stages": stages,
        },
    )
    assert nap.status_code == 201 and nap.json()["total_sleep_min"] == 190
    assert nap.json()["stages_recorded"] is True


# ------------------------------------------------------------------- vision ---


def test_vision_exam_and_physician_review(client, login):
    me, physician = login("ID-01"), login("ID-03")
    exam = client.get("/api/v1/vision/ID-01", headers=me).json()
    assert exam["status"] == "CRITICAL" and exam["worst_side"] == "right"
    assert exam["headline"] == "Right sheath elevated (5.9 mm)"
    assert exam["eyes"]["right"]["value"] == 5.9 and exam["eyes"]["left"]["value"] == 5.5
    assert exam["review"]["state"] == "PENDING_REVIEW"  # never approved by default
    assert exam["limits"]["alert_mm"] == 5.8
    labels = [p["label"] for p in exam["trend"]]
    assert labels[0] == "Baseline" and labels[-1] == "Day 47"
    assert all(p["kind"] in ("BASELINE", "EXAM") for p in exam["trend"])
    assert len(exam["care_plan"]) == 3

    assert client.post("/api/v1/vision/ID-01/review", headers=me, json={}).status_code == 403
    assert client.post("/api/v1/vision/ID-03/review", headers=physician, json={}).status_code == 403
    review = client.post(
        "/api/v1/vision/ID-01/review",
        headers=physician,
        json={"decision": "APPROVED", "notes_en": "Continue countermeasures."},
    )
    assert review.status_code == 201
    after = client.get("/api/v1/vision/ID-01", headers=me).json()["review"]
    assert after["state"] == "APPROVED" and after["text"] == "Reviewed by Dr. A. Okafor"

    healthy = client.get("/api/v1/vision/ID-03", headers=physician).json()
    assert healthy["status"] == "NOMINAL" and healthy["review"]["state"] == "NOT_REQUIRED"


# ------------------------------------------------------------- auscultation ---


def _wav(signal) -> tuple[bytes, str]:
    data = acoustics.write_wav(signal, 4000)
    return data, hashlib.sha256(data).hexdigest()


def _upload(client, headers, data, digest, organ="CARDIAC", site="mitral", noise=48.0):
    return client.post(
        "/api/v1/auscultation/samples",
        headers=headers,
        data={
            "organ_type": organ,
            "anatomical_site": site,
            "cabin_noise_dba": str(noise),
            "sha256_hex": digest,
        },
        files={"audio_file": ("sample.wav", data, "audio/wav")},
    )


def test_recording_is_analysed_stored_and_shown(client, login):
    me = login("ID-03")
    data, digest = _wav(acoustics.simulate_heart(72, 30, 4000, seed=5))
    saved = _upload(client, me, data, digest)
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["rate_per_min"] == pytest.approx(72, abs=3)  # measured from the audio itself
    assert body["rhythm_label"] == "Regular S1/S2 rhythm"

    lungs, lung_digest = _wav(acoustics.simulate_lungs(15, 30, 4000, seed=6))
    breath = _upload(client, me, lungs, lung_digest, organ="PULMONARY", site="upper_right")
    assert breath.json()["rate_per_min"] == pytest.approx(15, abs=1.5)

    results = client.get("/api/v1/auscultation/ID-03", headers=me).json()
    assert results["cardiac"]["rate_per_min"] == pytest.approx(72, abs=3)
    assert results["cardiac"]["sites_recorded"] == 1  # only what was actually recorded
    assert results["pulmonary"]["sites_recorded"] == 1
    assert len(results["cardiac"]["envelope"]) == acoustics.ENVELOPE_POINTS
    assert results["co2"]["limits_mmhg"]["alert"] == pytest.approx(4.0, abs=0.05)
    assert len(results["co2"]["trend"]) >= 20
    progress = client.get("/api/v1/auscultation/progress", headers=me).json()
    assert progress == {"CARDIAC": ["mitral"], "PULMONARY": ["upper_right"]}

    audio = client.get(f"/api/v1/auscultation/samples/{body['id']}/audio", headers=me)
    assert audio.status_code == 200 and hashlib.sha256(audio.content).hexdigest() == digest
    assert (
        client.get(
            f"/api/v1/auscultation/samples/{body['id']}/audio", headers=login("ID-04")
        ).status_code
        == 403
    )


def test_recording_gates(client, login):
    me = login("ID-03")
    data, digest = _wav(acoustics.simulate_heart(70, 30, 4000, seed=1))
    loud = _upload(client, me, data, digest, noise=58)
    assert loud.status_code == 422 and "too loud" in loud.json()["detail"]
    assert _upload(client, me, data, "0" * 64).status_code == 422  # damaged
    assert _upload(client, me, data, digest, site="upper_left").status_code == 422  # wrong spot
    short, short_digest = _wav(acoustics.simulate_heart(70, 12, 4000, seed=1))
    assert "30-second" in _upload(client, me, short, short_digest).json()["detail"]
    junk = b"not audio at all"
    assert _upload(client, me, junk, hashlib.sha256(junk).hexdigest()).status_code == 422


# ----------------------------------------------------- overview and streaks ---


def test_crew_overview_matches_the_seeded_stories(client):
    overview = client.get("/api/v1/crew-overview").json()
    crew = {c["id"]: c for c in overview["crew"]}
    assert [c["title_en"] for c in overview["crew"]] == [
        "Commander",
        "Flight Engineer",
        "Medical Officer",
        "Mission Specialist",
    ]
    assert crew["ID-03"]["status"] == "Optimal"
    assert crew["ID-02"]["status"] == "Attention"  # short sleep and raised pressure
    assert crew["ID-01"]["status"] == "Attention"  # open critical eye advisory
    assert crew["ID-04"]["status"] == "Nominal"  # post-spacewalk, sleep under target
    assert crew["ID-02"]["vitals"]["sleep_min_24h"] < 360
    assert crew["ID-04"]["work_shift"]["mode"] == "EVA"
    assert overview["readiness"]["sleep_below_count"] == 2
    assert 0 < overview["readiness"]["hydration_pct"] <= 100
    assert overview["cabin"]["status"] == "NOMINAL"
    # Any unacknowledged CRITICAL advisory (here Elena's eye) puts the cabin on alert.
    assert overview["cabin_mode"] == "critical"


def test_crew_streaks_follow_the_logged_habits(client, login):
    streaks = client.get("/api/v1/crew-streaks").json()
    crew = {c["id"]: c for c in streaks["crew"]}
    assert [crew[i]["active_streak_days"] for i in ("ID-01", "ID-02", "ID-03", "ID-04")] == [
        14,
        11,
        19,
        9,
    ]
    assert crew["ID-04"]["today_shield"] is True  # exterior work day protected by the shield
    assert crew["ID-02"]["today_compliant"] is False
    assert [h["label"] for h in crew["ID-04"]["habits"]][2] == "Post-EVA Rest"
    assert len(streaks["window"]) == 7 and streaks["window"][-1]["day_label"] == "D47"
    assert streaks["team"]["post_eva_rest"] == 1
    # Finishing the water goal updates the streak view straight away.
    me = login("ID-01")
    _post(client, me, [{"metric_key": "hydration_ml", "value_num": 600}])
    updated = client.get("/api/v1/crew-streaks").json()
    if updated["habits_date_utc"] == streaks["habits_date_utc"]:
        elena = next(c for c in updated["crew"] if c["id"] == "ID-01")
        assert elena["habits"][0]["pct"] == 100 and elena["habits_done_today"] == 4


# --------------------------------------------------- comms and environment ---


def test_comms_store_and_forward_with_signal_delay(client, login, db):
    me = login("ID-01")
    status = client.get("/api/v1/comms", headers=me).json()
    assert status["earth_latency_min"] == 12 and status["synchronized"] is True
    states = [m["state"] for m in status["messages"]]
    assert len(states) == 3 and states[-1] == "ARCHIVED"  # read messages age into the archive
    assert set(states) <= {"CONFIRMED", "ARCHIVED"}
    assert status["solar_weather"]["kp_label"] in ("Quiet conditions", "Unsettled conditions")

    queued = client.post("/api/v1/comms/packets", headers=me, json={"note_en": "All well."})
    assert queued.status_code == 201 and queued.json()["status"] == "QUEUED"
    bundle = json.loads(
        db.execute(
            "SELECT bundle_json FROM ground_outbox WHERE id = ?", (queued.json()["id"],)
        ).fetchone()[0]
    )
    assert bundle["schema"] == "spacescan.daily_summary.v1" and len(bundle["crew"]) == 4
    assert (
        client.get("/api/v1/comms", headers=me).json()["transmission_log"][0]["state"]
        == "IN TRANSIT"
    )

    from app.services.comms_service import process_ground_outbox

    later = to_iso(utc_now() + timedelta(minutes=13))
    assert process_ground_outbox(db, later)["delivered"] == 1
    much_later = to_iso(utc_now() + timedelta(minutes=30))
    assert process_ground_outbox(db, much_later)["acknowledged"] == 1
    db.commit()


def test_inbound_message_is_signed_delayed_and_confirmable(client, login, db):
    from tests.test_access_control import _signed

    raw, headers = _signed(
        {
            "title_en": "Hydration follow-up",
            "guidance_en": "Add 400 mL today.",
            "sender_en": "Dr. R. Miller · Flight Surgeon",
            "crew_id": "ID-01",
        }
    )
    assert (
        client.post(
            "/api/v1/comms/directives", content=raw, headers={"Content-Type": "application/json"}
        ).status_code
        == 401
    )
    sent = client.post("/api/v1/comms/directives", content=raw, headers=headers)
    assert sent.status_code == 202
    me = login("ID-01")
    titles = [m["title_en"] for m in client.get("/api/v1/comms", headers=me).json()["messages"]]
    assert "Hydration follow-up" not in titles  # still travelling

    from app.services.comms_service import process_ground_outbox

    process_ground_outbox(db, to_iso(utc_now() + timedelta(minutes=13)))
    db.execute(
        "UPDATE ground_outbox SET delivered_at_utc = ? WHERE id = ?",
        (to_iso(utc_now()), sent.json()["id"]),
    )
    db.commit()
    message = client.get("/api/v1/comms", headers=me).json()["messages"][0]
    assert message["title_en"] == "Hydration follow-up" and message["state"] == "NEW"
    confirmed = client.post(f"/api/v1/comms/messages/{message['id']}/confirm", headers=me)
    assert confirmed.json()["state"] == "CONFIRMED"


def test_cabin_reading_outside_limits_alerts_the_whole_crew(client, login, db):
    me = login("ID-04")
    calm = client.post(
        "/api/v1/environment",
        headers=me,
        json={
            "co2_ppm": 3600,
            "noise_dba": 48,
            "temp_c": 22,
            "humidity_pct": 45,
            "radiation_msv": 0.4,
        },
    )
    assert calm.status_code == 201 and calm.json()["alerts_created"] == []
    stuffy = client.post(
        "/api/v1/environment",
        headers=me,
        json={
            "co2_ppm": 5600,
            "noise_dba": 48,
            "temp_c": 28.5,
            "humidity_pct": 45,
            "radiation_msv": 0.4,
        },
    )
    created = stuffy.json()["alerts_created"]
    assert len(created) == 8  # CO2 and temperature, for each of the four crew members
    rows = db.execute(
        "SELECT DISTINCT severity, title_en FROM alerts WHERE id IN ({})".format(
            ",".join("?" * len(created))
        ),
        created,
    ).fetchall()
    titles = {r["title_en"]: r["severity"] for r in rows}
    assert titles["Cabin Carbon Dioxide high (4.26 mmHg)"] == "WARNING"
    assert titles["Cabin Temperature high (28.5 °C)"] == "WARNING"
    cabin = client.get("/api/v1/mission").json()["cabin"]
    assert cabin["status"] == "WARNING" and cabin["statuses"]["temp_c"] == "WARNING"
    repeat = client.post(
        "/api/v1/environment",
        headers=me,
        json={
            "co2_ppm": 5600,
            "noise_dba": 48,
            "temp_c": 28.5,
            "humidity_pct": 45,
            "radiation_msv": 0.4,
        },
    )
    assert repeat.json()["alerts_created"] == []
