"""API tests for the Notifications endpoints (D3-02)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import open_connection
from app.main import app as fastapi_app
from db.seed import seed_database

PINS = {"ID-01": "1042", "ID-02": "2084", "ID-03": "3190", "ID-04": "4275"}


@pytest.fixture()
def client(temp_db_path: Path):
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with TestClient(fastapi_app) as test_client:
        yield test_client


def _headers(client: TestClient, crew_id: str) -> dict[str, str]:
    login = client.post("/api/v1/auth/login", json={"crew_id": crew_id, "pin": PINS[crew_id]})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _db(temp_db_path: Path):
    return open_connection(temp_db_path)


def test_alerts_require_a_signed_in_crew_member(client) -> None:
    assert client.get("/api/v1/alerts").status_code == 401
    assert client.post("/api/v1/alerts/1/acknowledge").status_code == 401


def test_all_view_lists_own_advisories_first_by_severity_then_checks(
    client, temp_db_path: Path
) -> None:
    body = client.get("/api/v1/alerts", headers=_headers(client, "ID-01")).json()
    assert body["crew_id"] == "ID-01"
    kinds = [item["kind"] for item in body["items"]]
    order = ["ADVISORY", "SCHEDULED", "MISSION_CONTROL"]
    assert kinds == sorted(kinds, key=order.index)  # advisories, then checks, then messages
    advisories = [i for i in body["items"] if i["kind"] == "ADVISORY"]
    checks = [i for i in body["items"] if i["kind"] == "SCHEDULED"]
    severities = [a["severity"] for a in advisories]
    assert severities == sorted(severities, key=["CRITICAL", "WARNING", "INFO"].index)

    with _db(temp_db_path) as conn:
        open_alerts = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE crew_id = 'ID-01' AND acknowledged_at_utc IS NULL"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM scheduled_checks WHERE crew_id = 'ID-01' AND status = 'PENDING'"
        ).fetchone()[0]
    messages = sum(1 for k in kinds if k == "MISSION_CONTROL")
    assert body["counts"]["advisories"] == open_alerts and body["counts"]["checks"] == pending
    assert body["counts"]["all"] == open_alerts + pending + messages
    assert len(advisories) == open_alerts and len(checks) == pending
    assert pending >= 6  # one open check per type after the startup refresh

    step = advisories[0]["care_steps"][0]
    assert set(step) == {"title_en", "detail_en", "done_at_utc"}
    assert all(c["detail_en"] for c in checks)


def test_views_filter_by_kind(client) -> None:
    headers = _headers(client, "ID-01")
    advisories = client.get("/api/v1/alerts", params={"view": "advisories"}, headers=headers)
    checks = client.get("/api/v1/alerts", params={"view": "checks"}, headers=headers)
    assert {i["kind"] for i in advisories.json()["items"]} == {"ADVISORY"}
    assert {i["kind"] for i in checks.json()["items"]} == {"SCHEDULED"}
    bad = client.get("/api/v1/alerts", params={"view": "everything"}, headers=headers)
    assert bad.status_code == 422


def test_acknowledge_own_alert_hides_it_and_is_idempotent(client, temp_db_path: Path) -> None:
    headers = _headers(client, "ID-01")
    first = client.get("/api/v1/alerts", params={"view": "advisories"}, headers=headers).json()
    target = first["items"][0]["id"]

    ack = client.post(f"/api/v1/alerts/{target}/acknowledge", headers=headers)
    assert ack.status_code == 200
    stamp = ack.json()["acknowledged_at_utc"]
    assert stamp is not None
    again = client.post(f"/api/v1/alerts/{target}/acknowledge", headers=headers)
    assert again.json()["acknowledged_at_utc"] == stamp

    after = client.get("/api/v1/alerts", params={"view": "advisories"}, headers=headers).json()
    assert target not in [i["id"] for i in after["items"]]
    assert after["counts"]["advisories"] == first["counts"]["advisories"] - 1
    history = client.get(
        "/api/v1/alerts",
        params={"view": "advisories", "include_acknowledged": True},
        headers=headers,
    ).json()
    assert target in [i["id"] for i in history["items"]]

    with _db(temp_db_path) as conn:
        row = conn.execute("SELECT acknowledged_by FROM alerts WHERE id = ?", (target,)).fetchone()
    assert row["acknowledged_by"] == "ID-01"


def test_only_owner_or_physician_can_acknowledge(client, temp_db_path: Path) -> None:
    with _db(temp_db_path) as conn:
        alert_id = conn.execute(
            "SELECT id FROM alerts WHERE crew_id = 'ID-01' ORDER BY id LIMIT 1"
        ).fetchone()[0]
    other = client.post(f"/api/v1/alerts/{alert_id}/acknowledge",
                        headers=_headers(client, "ID-02"))
    assert other.status_code == 404
    physician = client.post(f"/api/v1/alerts/{alert_id}/acknowledge",
                            headers=_headers(client, "ID-03"))
    assert physician.status_code == 200
    missing = client.post("/api/v1/alerts/999999/acknowledge", headers=_headers(client, "ID-01"))
    assert missing.status_code == 404


def test_deferred_advisories_stay_hidden_during_rest_but_critical_shows(
    client, temp_db_path: Path
) -> None:
    now = datetime.now(UTC)
    start = (now - timedelta(hours=1)).strftime("%H:%M")
    end = (now + timedelta(hours=1)).strftime("%H:%M")
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    with _db(temp_db_path) as conn:
        conn.execute("UPDATE mission SET quiet_hours_start_utc = ?, quiet_hours_end_utc = ?",
                     (start, end))
        for severity, deferred in (("WARNING", 1), ("CRITICAL", 0)):
            conn.execute(
                """
                INSERT INTO alerts (crew_id, severity, category, title_en, message_en,
                                    recommended_actions_json, is_quiet_deferred, created_at_utc)
                VALUES ('ID-02', ?, 'VITALS', ?, 'Test message.', ?, ?, ?)
                """,
                (severity, f"Rest test {severity}", json.dumps(["Plain older step"]),
                 deferred, stamp),
            )
        conn.commit()

    body = client.get("/api/v1/alerts", params={"view": "advisories"},
                      headers=_headers(client, "ID-02")).json()
    assert body["quiet_hours"] == {"start_utc": start, "end_utc": end, "active": True}
    titles = [i["title_en"] for i in body["items"]]
    assert "Rest test CRITICAL" in titles
    assert "Rest test WARNING" not in titles
    critical = next(i for i in body["items"] if i["title_en"] == "Rest test CRITICAL")
    # Older rows stored plain sentences; they come back in the new step shape.
    assert critical["care_steps"] == [
        {"title_en": "Plain older step", "detail_en": "", "done_at_utc": None}]
