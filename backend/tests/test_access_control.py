"""RNF 3: public views stay public; personal health data needs the owner's PIN or the physician."""

import hashlib
import hmac
import json

import pytest

from app.config import GROUND_LINK_KEY

PUBLIC = [
    "/api/v1/health",
    "/api/v1/mission",
    "/api/v1/crew/profiles",
    "/api/v1/crew-overview",
    "/api/v1/crew-streaks",
    "/api/v1/metrics/catalog",
    "/api/v1/wiki/search",
    "/api/v1/wiki/emergency-index",
    "/api/v1/kit/drawers",
]
PRIVATE_GET = [
    "/api/v1/crew/ID-01/profile",
    "/api/v1/sleep/ID-01",
    "/api/v1/vision/ID-01",
    "/api/v1/auscultation/ID-01",
    "/api/v1/auscultation/progress",
    "/api/v1/measurements?crew_id=ID-01",
    "/api/v1/crew/ID-01/baselines",
    "/api/v1/comms",
    "/api/v1/alerts",
    "/api/v1/psych/profile",
    "/api/v1/diagnosis",
    "/api/v1/crew",
    "/api/v1/auth/me",
]
PRIVATE_POST = [
    "/api/v1/measurements",
    "/api/v1/sleep/sessions",
    "/api/v1/comms/packets",
    "/api/v1/comms/flush",
    "/api/v1/environment",
    "/api/v1/psych/checkins",
    "/api/v1/cognitive/sessions",
    "/api/v1/diagnosis/anomalies",
    "/api/v1/mission/stage",
    "/api/v1/crew",
    "/api/v1/auth/stream-token",
    "/api/v1/vision/ID-01/review",
    "/api/v1/auscultation/samples",
]


@pytest.mark.parametrize("path", PUBLIC)
def test_public_views_need_no_session(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", PRIVATE_GET)
def test_private_reads_need_a_session(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", PRIVATE_POST)
def test_private_writes_need_a_session(client, path):
    assert client.post(path, json={}).status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/crew/ID-01/profile",
        "/api/v1/sleep/ID-01",
        "/api/v1/vision/ID-01",
        "/api/v1/auscultation/ID-01",
        "/api/v1/measurements?crew_id=ID-01",
        "/api/v1/psych/profile?crew_id=ID-01",
    ],
)
def test_only_owner_or_physician_reads_health_records(client, login, path):
    assert client.get(path, headers=login("ID-01")).status_code == 200
    assert client.get(path, headers=login("ID-04")).status_code == 403
    assert client.get(path, headers=login("ID-03")).status_code == 200  # physician


def test_public_views_carry_no_individual_clinical_detail(client):
    overview = client.get("/api/v1/crew-overview").json()
    assert set(overview["crew"][0]["vitals"]) <= {
        "resting_hr_bpm",
        "hrv_rmssd_ms",
        "spo2_pct",
        "sleep_min_24h",
        "sleep_hours_24h",
        "sleep_target_min",
        "resting_hr_status",
        "hrv_status",
        "spo2_status",
    }
    text = json.dumps(
        [
            overview,
            client.get("/api/v1/crew-streaks").json(),
            client.get("/api/v1/crew/profiles").json(),
        ]
    )
    for private in ("optic_sheath", "blood_glucose", "pin_hash", "mood", "stress"):
        assert private not in text


def test_public_stream_is_cabin_only_and_vitals_need_a_pass(client, login):
    assert client.get("/api/v1/stream/vitals").status_code == 422
    assert client.get("/api/v1/stream/vitals?token=not-a-real-pass").status_code == 401
    session = login("ID-01")["Authorization"].removeprefix("Bearer ")
    # A normal session token is not a stream pass, and a stream pass is not a session.
    assert client.get(f"/api/v1/stream/vitals?token={session}").status_code == 401
    stream_pass = client.post("/api/v1/auth/stream-token", headers=login("ID-01")).json()
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {stream_pass['stream_token']}"}
        ).status_code
        == 401
    )


def test_login_does_not_reveal_which_profiles_exist(client):
    wrong_pin = client.post("/api/v1/auth/login", json={"crew_id": "ID-01", "pin": "0000"})
    unknown = client.post("/api/v1/auth/login", json={"crew_id": "ID-99", "pin": "0000"})
    assert wrong_pin.status_code == unknown.status_code == 401


def test_pin_lockout_after_five_attempts(client):
    for _ in range(4):
        assert (
            client.post("/api/v1/auth/login", json={"crew_id": "ID-04", "pin": "0000"}).status_code
            == 401
        )
    assert (
        client.post("/api/v1/auth/login", json={"crew_id": "ID-04", "pin": "0000"}).status_code
        == 423
    )
    assert (
        client.post("/api/v1/auth/login", json={"crew_id": "ID-04", "pin": "4275"}).status_code
        == 423
    )


def test_crew_management_is_operator_only(client, login):
    new = {
        "id": "ID-05",
        "code": "ID·05",
        "full_name": "Test Person",
        "role": "ASTRONAUT",
        "pin": "5555",
    }
    assert client.post("/api/v1/crew", json=new, headers=login("ID-01")).status_code == 403
    assert client.post("/api/v1/crew", json=new, headers=login("ID-03")).status_code == 403
    operator = login("ID-02")
    assert client.post("/api/v1/crew", json=new, headers=operator).status_code == 201
    assert client.post("/api/v1/crew", json=new, headers=operator).status_code == 409
    assert len(client.get("/api/v1/crew", headers=operator).json()) == 5
    # The only operator cannot be demoted or deactivated.
    assert (
        client.patch("/api/v1/crew/ID-02", json={"role": "ASTRONAUT"}, headers=operator).status_code
        == 409
    )
    assert (
        client.patch("/api/v1/crew/ID-02", json={"is_active": False}, headers=operator).status_code
        == 409
    )


def test_role_change_ends_the_old_session(client, login):
    operator, pilot = login("ID-02"), login("ID-01")
    assert client.get("/api/v1/auth/me", headers=pilot).status_code == 200
    assert (
        client.patch("/api/v1/crew/ID-01", json={"role": "ASTRONAUT"}, headers=operator).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me", headers=pilot).status_code == 401
    assert (
        client.patch("/api/v1/crew/ID-04", json={"is_active": False}, headers=operator).status_code
        == 200
    )
    assert (
        client.post("/api/v1/auth/login", json={"crew_id": "ID-04", "pin": "4275"}).status_code
        == 401
    )


def _signed(body: dict) -> tuple[bytes, dict]:
    raw = json.dumps(body).encode()
    signature = hmac.new(GROUND_LINK_KEY.encode(), raw, hashlib.sha256).hexdigest()
    return raw, {"X-Ground-Signature": signature, "Content-Type": "application/json"}


def test_ground_orders_need_a_valid_signature_and_respect_the_signal_delay(client, login, db):
    order = {
        "action": "CREATE",
        "crew_id": "ID-07",
        "code": "ID·07",
        "full_name": "Remote Hire",
        "role": "OPERATOR",
        "pin": "7777",
    }
    raw, headers = _signed(order)
    unsigned = client.post(
        "/api/v1/crew/ground-sync", content=raw, headers={"Content-Type": "application/json"}
    )
    assert unsigned.status_code == 401
    forged = client.post(
        "/api/v1/crew/ground-sync", content=raw, headers={**headers, "X-Ground-Signature": "0" * 64}
    )
    assert forged.status_code == 401

    queued = client.post("/api/v1/crew/ground-sync", content=raw, headers=headers)
    assert queued.status_code == 202 and queued.json()["applies_after_min"] == 12
    assert db.execute("SELECT 1 FROM crew_members WHERE id = 'ID-07'").fetchone() is None
    stored = db.execute("SELECT bundle_json FROM ground_outbox ORDER BY id DESC LIMIT 1").fetchone()
    assert "7777" not in stored["bundle_json"]  # the PIN never sits in the queue in clear

    from datetime import timedelta

    from app.services.comms_service import process_ground_outbox
    from app.services.mission_clock import to_iso, utc_now

    process_ground_outbox(db, to_iso(utc_now() + timedelta(minutes=13)))
    db.commit()
    assert (
        db.execute("SELECT role FROM crew_members WHERE id = 'ID-07'").fetchone()["role"]
        == "OPERATOR"
    )
    assert (
        client.post("/api/v1/auth/login", json={"crew_id": "ID-07", "pin": "7777"}).status_code
        == 200
    )
    duplicate = client.post("/api/v1/crew/ground-sync", content=raw, headers=headers)
    assert duplicate.status_code == 409


def test_mission_stage_moves_forward_only_by_the_operator(client, login):
    assert (
        client.post(
            "/api/v1/mission/stage", json={"stage": "RETURN"}, headers=login("ID-01")
        ).status_code
        == 403
    )
    operator = login("ID-02")
    assert (
        client.post("/api/v1/mission/stage", json={"stage": "LAUNCH"}, headers=operator).status_code
        == 409
    )
    moved = client.post("/api/v1/mission/stage", json={"stage": "RETURN"}, headers=operator)
    assert moved.status_code == 200 and moved.json()["current_stage"] == "RETURN"
    saved = client.post(
        "/api/v1/measurements",
        headers=login("ID-01"),
        json={"items": [{"metric_key": "resting_hr_bpm", "value_num": 63}]},
    )
    assert saved.status_code == 201 and saved.json()["mission_stage"] == "RETURN"
    profile = client.get("/api/v1/crew/ID-01/profile", headers=login("ID-01")).json()
    assert profile["mission_stage"] == "RETURN"
    assert profile["stage_comparison"]["resting_hr_bpm"]["RETURN"] == 63
