"""M9: what each role adds on top of the astronaut base (pilot readiness, the physician's
patients and clinical record, the operator's crew administration) and the ground station."""

from app.config import GROUND_LINK_KEY
from app.db import open_connection
from app.services.pilot_readiness import classify, focus_index, reaction_score, recovery_days

# ------------------------------------------------------------------- pilot ---


def test_pilot_readiness_access_and_contents(client, login) -> None:
    pilot, doctor, engineer = login("ID-01"), login("ID-03"), login("ID-02")
    own = client.get("/api/v1/crew/ID-01/pilot-readiness", headers=pilot)
    assert own.status_code == 200
    body = own.json()
    assert client.get("/api/v1/crew/ID-01/pilot-readiness", headers=doctor).status_code == 200
    assert client.get("/api/v1/crew/ID-01/pilot-readiness", headers=engineer).status_code == 403
    assert client.get("/api/v1/crew/ID-02/pilot-readiness", headers=doctor).status_code == 409

    # Measured from the logged reaction tests; retention has no test yet and is not invented.
    assert body["retention"] == {"cognitive_retention_pct": None, "measured": False,
                                 "note_en": "Not measured yet"}
    assert 0 <= body["attention"]["sustained_attention_pct"] <= 100
    assert body["attention"]["attention_lapses"] >= 0
    assert 0 <= body["focus"]["focus_index_score"] <= 100
    assert body["sensorimotor"]["reaction_time_ms"] > 100
    assert body["gate"]["visual_acuity_text"].startswith("20/")
    assert body["tests_used"] == 5 and len(body["history"]) >= 5
    assert body["state"] in ("CLEARED", "CROSS_CHECK", "RESTRICTED")
    assert 0 <= body["score"] <= 100


def test_pilot_states_use_stricter_thresholds() -> None:
    assert classify(90, 7.5, 20) == "CLEARED"
    assert classify(84, 7.5, 20) == "CROSS_CHECK"
    assert classify(69, 7.5, 20) == "RESTRICTED"
    assert classify(95, 5.5, 20) == "RESTRICTED"  # under six hours of sleep
    assert classify(95, 7.5, 40) == "CROSS_CHECK"  # vision worse than 20/30
    assert classify(95, None, 20) == "CROSS_CHECK"  # sleep not logged
    assert reaction_score(250) == 100 and reaction_score(450) == 0
    assert focus_index([100, 100], [300, 300], [0, 0]) == 100
    assert focus_index([100, 100], [200, 400], [2, 2]) < 80
    tests = [{"reaction_ms": v, "recorded_at_utc": f"2026-11-0{i + 1}T08:00:00Z"}
             for i, v in enumerate([270, 268, 400, 330, 272])]
    assert recovery_days(tests) == 2.0  # slowest on day 3, back to usual on day 5


# --------------------------------------------------------------- physician ---


def test_patients_and_clinical_record_are_for_the_physician(client, login) -> None:
    doctor, pilot = login("ID-03"), login("ID-01")
    assert client.get("/api/v1/crew/patients", headers=pilot).status_code == 403
    patients = client.get("/api/v1/crew/patients", headers=doctor).json()
    assert [p["id"] for p in patients] == ["ID-01", "ID-02", "ID-03", "ID-04"]
    elena = patients[0]
    assert elena["short_name"] == "E. Vargas" and elena["open_critical"] >= 1

    assert client.get("/api/v1/crew/ID-01/clinical-history", headers=pilot).status_code == 403
    record = client.get("/api/v1/crew/ID-01/clinical-history", headers=doctor).json()
    assert record["crew"]["full_name"] == "Elena Vargas"
    assert {"baselines", "timeline", "labs", "sleep", "eyes", "sounds", "alerts", "findings"} \
        <= set(record)
    assert any(b["z"] is not None for b in record["baselines"])
    assert record["sleep"] and record["eyes"] and isinstance(record["sounds"], list)
    assert all(s["audio_path"].endswith("/audio") for s in record["sounds"])
    # Acknowledged advisories stay in the record.
    assert any(a["acknowledged_at_utc"] for a in record["alerts"])
    assert any(a["acknowledged_at_utc"] is None for a in record["alerts"])

    labs = client.get("/api/v1/crew/ID-01/clinical-history", params={"category": "LABS"},
                      headers=doctor).json()
    assert labs["timeline"] and {r["category"] for r in labs["timeline"]} == {"LABS"}
    assert client.get("/api/v1/crew/ID-01/clinical-history", params={"category": "NOPE"},
                      headers=doctor).status_code == 422


def test_physician_reads_any_patient_screens(client, login) -> None:
    doctor = login("ID-03")
    for path in ("/crew/ID-02/profile", "/vision/ID-02", "/sleep/ID-02", "/auscultation/ID-02",
                 "/streaks/ID-02"):
        assert client.get(f"/api/v1{path}", headers=doctor).status_code == 200, path
    psych = client.get("/api/v1/psych/profile", params={"crew_id": "ID-02"}, headers=doctor)
    assert psych.status_code == 200
    # The physician may run the pattern scan for any patient.
    scan = client.post("/api/v1/diagnosis/anomalies", json={"crew_id": "ID-04"}, headers=doctor)
    assert scan.status_code == 200


# ---------------------------------------------------------------- operator ---


def test_operator_edits_resets_pin_and_unlocks(client, login) -> None:
    operator = login("ID-02")
    edit = client.patch("/api/v1/crew/ID-04", headers=operator,
                        json={"role": "PILOT", "sex": "M", "height_cm": 181, "blood_type": "B+",
                              "title_en": "Backup Pilot", "pin": "9876"})
    assert edit.status_code == 200
    member = edit.json()
    assert member["role"] == "PILOT" and member["height_cm"] == 181
    assert member["title_en"] == "Backup Pilot"
    old = client.post("/api/v1/auth/login", json={"crew_id": "ID-04", "pin": "4275"})
    new = client.post("/api/v1/auth/login", json={"crew_id": "ID-04", "pin": "9876"})
    assert old.status_code == 401 and new.status_code == 200

    for _ in range(5):
        client.post("/api/v1/auth/login", json={"crew_id": "ID-01", "pin": "0000"})
    assert client.post("/api/v1/auth/login",
                       json={"crew_id": "ID-01", "pin": "1042"}).status_code == 423
    assert client.patch("/api/v1/crew/ID-01", headers=operator,
                        json={"unlock_account": True}).status_code == 200
    assert client.post("/api/v1/auth/login",
                       json={"crew_id": "ID-01", "pin": "1042"}).status_code == 200

    # The only operator can neither be deactivated nor lose the role.
    assert client.patch("/api/v1/crew/ID-02", headers=operator,
                        json={"is_active": False}).status_code == 409
    assert client.patch("/api/v1/crew/ID-02", headers=operator,
                        json={"role": "ASTRONAUT"}).status_code == 409
    assert client.patch("/api/v1/crew/ID-04", headers=login("ID-03"),
                        json={"pin": "1111"}).status_code == 403


def test_closing_the_launch_stage_freezes_baselines(client, login) -> None:
    operator = login("ID-02")
    with open_connection() as conn:
        conn.execute("UPDATE mission SET current_stage = 'LAUNCH' WHERE id = 1")
        conn.execute("DELETE FROM baselines WHERE crew_id = 'ID-04'")
    moved = client.post("/api/v1/mission/stage", json={"stage": "MISSION"}, headers=operator)
    assert moved.status_code == 200 and moved.json()["baselines_frozen"] > 0
    with open_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM baselines WHERE crew_id = 'ID-04'"
                            ).fetchone()[0] > 0
    assert client.post("/api/v1/mission/stage", json={"stage": "LAUNCH"},
                       headers=operator).status_code == 409


# ---------------------------------------------------------- ground station ---


def _ground(client) -> dict[str, str]:
    session = client.post("/api/v1/ground/session", json={"link_key": GROUND_LINK_KEY})
    assert session.status_code == 200
    return {"Authorization": f"Bearer {session.json()['access_token']}"}


def test_ground_session_is_separate_from_crew_sessions(client, login) -> None:
    assert client.post("/api/v1/ground/session",
                       json={"link_key": "not-the-key-at-all"}).status_code == 401
    ground = _ground(client)
    assert client.get("/api/v1/comms", headers=ground).status_code == 401
    assert client.get("/api/v1/comms/ground/overview", headers=login("ID-02")).status_code == 401
    assert client.get("/api/v1/comms/ground/overview").status_code == 401


def test_ground_overview_receives_everything_sent_down(client, login) -> None:
    ground = _ground(client)
    client.post("/api/v1/comms/packets", json={"packet_type": "CLINICAL_REPORT"},
                headers=login("ID-03"))
    client.post("/api/v1/comms/ground/flush", headers=ground)
    overview = client.get("/api/v1/comms/ground/overview", headers=ground).json()
    assert len(overview["crew"]) == 4
    first = overview["crew"][0]
    assert {"vitals", "psych", "vision", "body", "alerts", "streak_days"} <= set(first)
    received = [p for p in overview["packets"] if p["state"] == "RECEIVED"]
    assert received and all(p["bundle"] for p in received)
    assert any(p["packet_type"] == "CLINICAL_REPORT" for p in received)
    assert all(p["bundle"] is None for p in overview["packets"] if p["state"] != "RECEIVED")


def test_ground_adds_crew_and_sends_guidance_after_the_pass(client, login) -> None:
    ground = _ground(client)
    order = client.post("/api/v1/comms/ground/crew", headers=ground, json={
        "action": "CREATE", "crew_id": "ID-05", "code": "ID·05", "full_name": "Nova Reyes",
        "role": "ASTRONAUT", "pin": "5555", "sex": "F", "age": 31, "height_cm": 166})
    assert order.status_code == 202 and order.json()["applies_after_min"] > 0
    guidance = client.post("/api/v1/comms/ground/directives", headers=ground, json={
        "crew_id": "ID-04", "sender_en": "Flight Surgeon", "title_en": "Hydration check",
        "guidance_en": "Drink 500 mL of water before the next shift."})
    assert guidance.status_code == 202

    uplink = client.get("/api/v1/comms/ground/overview", headers=ground).json()["uplink"]
    assert {u["state"] for u in uplink[:2]} == {"IN TRANSIT"}
    assert "pin_hash" not in str(uplink)
    assert client.post("/api/v1/auth/login",
                       json={"crew_id": "ID-05", "pin": "5555"}).status_code == 401

    client.post("/api/v1/comms/ground/flush", headers=ground)
    assert client.post("/api/v1/auth/login",
                       json={"crew_id": "ID-05", "pin": "5555"}).status_code == 200
    with open_connection() as conn:
        nova = conn.execute("SELECT sex, height_cm FROM crew_members WHERE id = 'ID-05'"
                            ).fetchone()
    assert nova["sex"] == "F" and nova["height_cm"] == 166
    messages = client.get("/api/v1/comms", headers=login("ID-04")).json()["messages"]
    assert messages[0]["title_en"] == "Hydration check"

    assert client.post("/api/v1/comms/ground/crew", headers=ground, json={
        "action": "DEACTIVATE", "crew_id": "ID-02"}).status_code == 409  # last operator
