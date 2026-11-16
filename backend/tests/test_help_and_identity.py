"""Shared base: parameter help text, neutral mission identity and the live change feed."""

import base64
import re
from pathlib import Path

from app.services import change_feed, reference_ranges

BACKEND = Path(__file__).resolve().parents[1]
RESTRICTED = [base64.b64decode(w).decode() for w in ("bmFzYQ==", "Y2hpbmE=", "Y2hpbmVzZQ==")]
SPANISH = re.compile(
    r"\b(?:usuario|guardar|fecha|paciente|sueño|tripulante|medición|pantalla|también|está)\b|[ñáéíóú¿¡]",
    re.IGNORECASE,
)
JARGON = re.compile(
    r"\b(sqlite|json|onnx|ollama|cnn|llm|neural|autoencoder|python)\b", re.IGNORECASE
)


def test_every_parameter_has_plain_english_help():
    entries = reference_ranges.help_entries()
    keys = [e["key"] for e in entries]
    assert len(keys) == len(set(keys)), "help keys must be unique"
    catalog = {m["metric_key"] for m in reference_ranges.load_reference()["metrics"]}
    assert catalog <= set(keys)
    restricted = re.compile(rf"\b({'|'.join(RESTRICTED)})\b", re.IGNORECASE)
    for entry in entries:
        for field in reference_ranges.HELP_FIELDS:
            text = entry[field]
            assert text and len(text.strip()) >= 20, (entry["key"], field)
            assert not restricted.search(text), (entry["key"], field)
            assert not SPANISH.search(text), (entry["key"], field)
            assert not JARGON.search(text), (entry["key"], field)


def test_help_endpoint_is_public(client):
    response = client.get("/api/v1/metrics/help")
    assert response.status_code == 200
    items = {item["key"]: item for item in response.json()}
    assert items["spo2_pct"]["nominal_min"] == 95.0
    assert items["sleep_score"]["summary_en"]


def test_mission_identity_is_neutral(client):
    mission = client.get("/api/v1/mission").json()["mission"]
    assert mission["mission_code"] == "DSM-01"


def test_backend_carries_no_retired_identity():
    pattern = re.compile(r"ares[\s_-]*vii", re.IGNORECASE)
    for folder in ("app", "db", "tests"):
        for file in (BACKEND / folder).rglob("*"):
            if file.suffix in {".py", ".json", ".sql"} and file.name != Path(__file__).name:
                assert not pattern.search(file.read_text(encoding="utf-8")), file


def test_change_feed_reports_domains_since_last_read():
    start = change_feed.current()
    change_feed.publish(*change_feed.domains_for_path("/api/v1/measurements"))
    change_feed.publish("alerts", "not-a-domain")
    sequence, changed = change_feed.changes_since(start)
    assert sequence == start + 2
    assert changed == ["alerts", "streaks", "vision", "vitals"]
    assert change_feed.changes_since(sequence) == (sequence, [])
    assert change_feed.domains_for_path("/api/v1/auth/login") == ()


def test_successful_write_is_announced(client, login):
    headers = login("ID-01")
    start = change_feed.current()
    response = client.post(
        "/api/v1/measurements",
        headers=headers,
        json={"items": [{"metric_key": "resting_hr_bpm", "value_num": 62}]},
    )
    assert response.status_code in (200, 201), response.text
    _, changed = change_feed.changes_since(start)
    assert "vitals" in changed and "alerts" in changed
