"""M8: the medical guide always works, it grows during the mission (promoted cases and
physician-written protocols), and the five advisory rules work end to end."""

from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import init_db, open_connection
from app.main import app as fastapi_app
from app.services.alert_rules import Baseline, adverse_trend
from app.services.diagnosis import scan_crew_member
from app.services.guide import search_articles
from app.services.mission_clock import to_iso, utc_now
from db.seed import seed_database

PINS = {"ID-01": "1042", "ID-02": "2084", "ID-03": "3190", "ID-04": "4275"}

PROTOCOL = {
    "title_en": "Dry Skin and Cracked Hands",
    "category_en": "Skin Care",
    "drawer_code": "DRAWER A1",
    "steps": [
        {"title_en": "Wash gently", "detail_en": "Rinse the hands with lukewarm water only."},
        {"title_en": "Apply barrier cream", "detail_en": "Rub a thin layer over the cracks."},
        {"title_en": "Wear soft gloves", "detail_en": "Keep the cream on during the rest period."},
    ],
    "escalation_en": "Call the physician if the cracks bleed, swell or feel hot.",
}


@pytest.fixture()
def client(temp_db_path: Path):
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH,
                  with_audio=False)
    with TestClient(fastapi_app) as test_client:
        yield test_client


def _headers(client: TestClient, crew_id: str) -> dict[str, str]:
    login = client.post("/api/v1/auth/login", json={"crew_id": crew_id, "pin": PINS[crew_id]})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _post(client, headers, items, **extra):
    return client.post("/api/v1/measurements", headers=headers, json={"items": items, **extra})


def _drawer(client) -> str:
    return client.get("/api/v1/kit/drawers").json()["drawers"][0]["code"]


# ------------------------------------------------------------------ guide ---

def test_guide_is_filled_on_any_new_database(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    init_db(path)
    with open_connection(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM wiki_articles").fetchone()[0] >= 10
        assert conn.execute("SELECT COUNT(*) FROM kit_drawers").fetchone()[0] >= 4
        assert search_articles(conn, "headache")  # the full-text index is in step
    init_db(path)  # running again never duplicates anything
    with open_connection(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM wiki_articles").fetchone()[0] >= 10


def test_opening_the_guide_without_words_lists_every_protocol(client) -> None:
    found = client.get("/api/v1/wiki/search").json()
    with open_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM wiki_articles").fetchone()[0]
    assert len(found["results"]) == total and found["categories"]
    first = found["results"][0]
    assert first["origin"] == "shipped" and first["mission_protocol"] is False
    assert client.get(f"/api/v1/wiki/articles/{first['id']}").status_code == 200


# ---------------------------------------------------- evolving guide -------

def test_physician_writes_a_mission_protocol_found_by_any_word(client) -> None:
    doctor = _headers(client, "ID-03")
    body = {**PROTOCOL, "drawer_code": _drawer(client)}
    assert client.post("/api/v1/wiki/articles", json=body, headers=_headers(client, "ID-01")
                       ).status_code == 403
    created = client.post("/api/v1/wiki/articles", json=body, headers=doctor)
    assert created.status_code == 201
    article = created.json()
    assert article["id"].startswith("wiki-mission-")
    assert article["origin"] == "physician" and article["mission_protocol"] is True
    assert article["assisted"] is False
    assert article["source_en"].startswith("Mission protocol by Dr.")
    for word in ("cracked", "barrier", "gloves", "bleed"):
        found = client.get("/api/v1/wiki/search", params={"q": word}).json()["results"]
        ids = [a["id"] for a in found]
        assert article["id"] in ids, word
    assert "Skin Care" in client.get("/api/v1/wiki/search").json()["categories"]
    # Mission protocols come first in the catalog.
    assert client.get("/api/v1/wiki/search").json()["results"][0]["id"] == article["id"]

    # It can be updated; shipped protocols never change on board.
    edited = client.put(f"/api/v1/wiki/articles/{article['id']}", headers=doctor,
                        json={**body, "title_en": "Dry Skin and Split Fingertips"})
    assert edited.status_code == 200 and "Split" in edited.json()["title_en"]
    assert article["id"] in [a["id"] for a in client.get(
        "/api/v1/wiki/search", params={"q": "fingertips"}).json()["results"]]
    assert client.put("/api/v1/wiki/articles/wiki-co2-01", headers=doctor, json=body
                      ).status_code == 422


@pytest.mark.parametrize("change", [
    {"title_en": "Piel seca y manos agrietadas"},  # not English
    {"title_en": "Cuidado de la piel"},
    {"escalation_en": "Call the physician if the json sensor fails."},  # technical term
    {"drawer_code": "DRAWER Z9"},  # not in the medical kit
    {"steps": PROTOCOL["steps"][:2]},  # fewer than three steps
])
def test_mission_protocol_text_is_checked(client, change) -> None:
    body = {**PROTOCOL, "drawer_code": _drawer(client), **change}
    response = client.post("/api/v1/wiki/articles", json=body, headers=_headers(client, "ID-03"))
    assert response.status_code == 422


def test_promoted_case_is_marked_and_searchable(client) -> None:
    offline = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    with open_connection() as conn:
        finding = scan_crew_member(conn, "ID-01", client=offline)["diagnosis"]
        conn.commit()
    assert finding is not None
    result = client.post(f"/api/v1/diagnosis/{finding['id']}/review",
                         json={"decision": "PROMOTED_TO_GUIDE"}, headers=_headers(client, "ID-03"))
    assert result.status_code == 200
    article_id = result.json()["guide_article_id"]
    article = client.get(f"/api/v1/wiki/articles/{article_id}").json()
    assert article["source_en"] == "Mission-validated clinical case (Physician approved)"
    assert article["assisted"] is True and article["origin"] == "mission_case"
    assert article["mission_protocol"] is True and article["drawer_code"]
    assert all(set(step) == {"title_en", "detail_en"} for step in article["steps"])
    word = article["steps"][0]["title_en"].split()[-1]
    found = client.get("/api/v1/wiki/search", params={"q": word}).json()["results"]
    assert article_id in [a["id"] for a in found]


# ----------------------------------------------------- the five rules ------

def test_adverse_trend_needs_a_steady_meaningful_harmful_move() -> None:
    assert adverse_trend([4.30, 4.46, 4.62], "up", 0.15) == "up"
    assert adverse_trend([4.30, 4.46, 4.62], "down", 0.15) is None  # harmless direction
    assert adverse_trend([4.30, 4.50, 4.45], "up", 0.15) is None  # not steady
    assert adverse_trend([4.30, 4.35, 4.40], "up", 0.15) is None  # within repeatability
    assert adverse_trend([80, 72, 64], "down", 6.0) == "down"
    assert adverse_trend([80, 72, 64], "both", 6.0) is None  # no single harmful side
    assert adverse_trend([4.3, 4.6], "up", 0.15) is None  # needs three readings
    near = Baseline(mean_val=4.6, std_dev=0.1, sample_count=10)
    assert adverse_trend([4.3, 4.46, 4.62], "up", 0.15, near) is None  # back at baseline


def _baseline(crew_id: str, metric: str) -> tuple[float, float]:
    with open_connection() as conn:
        row = conn.execute("SELECT mean_val, std_dev FROM baselines WHERE crew_id = ? AND "
                           "metric_key = ?", (crew_id, metric)).fetchone()
    return float(row["mean_val"]), float(row["std_dev"] or 0.0)


def _alert(alert_id: int) -> dict:
    with open_connection() as conn:
        return dict(conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone())


def test_rule_1_fixed_limits_raise_critical_and_turn_the_cabin_red(client) -> None:
    pilot = _headers(client, "ID-04")
    saved = _post(client, pilot, [{"metric_key": "spo2_pct", "value_num": 86}]).json()
    alert = _alert(saved["alerts_created"][0])
    assert alert["severity"] == "CRITICAL" and alert["wiki_article_id"]
    assert client.get("/api/v1/mission").json()["cabin_mode"] == "critical"


def test_rule_2_personal_drift_inside_the_range_is_a_quiet_note(client) -> None:
    mean, std = _baseline("ID-03", "resting_hr_bpm")
    value = round(mean + 2.4 * max(std, 3.0))
    saved = _post(client, _headers(client, "ID-03"),
                  [{"metric_key": "resting_hr_bpm", "value_num": value}]).json()
    assert [_alert(i)["severity"] for i in saved["alerts_created"]] == ["INFO"]
    assert "personal baseline" in _alert(saved["alerts_created"][0])["message_en"]


def test_rule_3_steady_rise_over_three_readings(client) -> None:
    doctor = _headers(client, "ID-03")
    mean, std = _baseline("ID-03", "optic_sheath_right_mm")
    last = round(mean + 1.5 * max(std, 0.15), 2)
    now = utc_now()
    created = []
    for minutes, value in ((3, last - 0.32), (2, last - 0.16), (1, last)):
        saved = _post(client, doctor, [{"metric_key": "optic_sheath_right_mm",
                                        "value_num": round(value, 2)}],
                      recorded_at_utc=to_iso(now - timedelta(minutes=minutes)))
        assert saved.status_code == 201
        created += saved.json()["alerts_created"]
    assert len(created) == 1
    alert = _alert(created[0])
    assert alert["severity"] == "INFO" and "rising steadily" in alert["title_en"]
    assert "last 3 readings" in alert["message_en"]


def test_rule_4_quiet_hours_defer_notes_but_never_critical(client) -> None:
    night = (utc_now() - timedelta(days=1)).replace(hour=23, minute=10, second=0, microsecond=0)
    doctor = _headers(client, "ID-03")
    mean, std = _baseline("ID-03", "resting_hr_bpm")
    note = _post(client, doctor, [{"metric_key": "resting_hr_bpm",
                                   "value_num": round(mean + 2.4 * max(std, 3.0))}],
                 recorded_at_utc=to_iso(night)).json()
    assert _alert(note["alerts_created"][0])["is_quiet_deferred"] == 1
    urgent = _post(client, doctor, [{"metric_key": "spo2_pct", "value_num": 86}],
                   recorded_at_utc=to_iso(night + timedelta(minutes=5))).json()
    alert = _alert(urgent["alerts_created"][0])
    assert alert["severity"] == "CRITICAL" and alert["is_quiet_deferred"] == 0
    assert client.get("/api/v1/mission").json()["cabin_mode"] == "critical"


def test_rule_5_steps_guide_link_and_acknowledge_restore_the_cabin(client) -> None:
    me = _headers(client, "ID-01")
    listing = client.get("/api/v1/alerts", params={"view": "advisories"}, headers=me).json()
    critical = [a for a in listing["items"] if a["severity"] == "CRITICAL"]
    assert critical and client.get("/api/v1/mission").json()["cabin_mode"] == "critical"

    first = critical[0]
    done = client.post(f"/api/v1/alerts/{first['id']}/steps/0/complete", headers=me).json()
    stamp = _alert(first["id"])["steps_done_json"]
    assert '"0": "20' in stamp and stamp.rstrip('"}').endswith("Z")
    assert done["id"] == first["id"]
    guide = first.get("guide_article_id")
    assert guide and client.get(f"/api/v1/wiki/articles/{guide}").status_code == 200

    before = listing["counts"]["advisories"]
    client.post(f"/api/v1/alerts/{first['id']}/acknowledge", headers=me)
    after = client.get("/api/v1/alerts", params={"view": "advisories"}, headers=me).json()
    assert after["counts"]["advisories"] == before - 1
    assert _alert(first["id"])["acknowledged_at_utc"]

    # Once every CRITICAL advisory on board is acknowledged the cabin returns to nominal.
    doctor = _headers(client, "ID-03")
    with open_connection() as conn:
        open_ids = [r[0] for r in conn.execute(
            "SELECT id FROM alerts WHERE severity = 'CRITICAL' AND acknowledged_at_utc IS NULL")]
    for alert_id in open_ids:
        assert client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=doctor
                           ).status_code == 200
    assert client.get("/api/v1/mission").json()["cabin_mode"] == "nominal"
