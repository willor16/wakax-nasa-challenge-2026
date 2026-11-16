"""Tests for the medical guide search and kit locator (D3-06)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import open_connection
from app.main import app as fastapi_app
from app.services.guide import (
    build_match_query,
    emergency_index,
    get_article,
    kit_drawers,
    normalize_steps,
    search_articles,
)
from db.seed import seed_database


@pytest.fixture()
def conn(temp_db_path: Path):
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with open_connection(temp_db_path) as connection:
        yield connection


def test_match_query_is_safe_and_prefix_based() -> None:
    assert build_match_query("elevated cabin CO2 headache") == (
        '"elevated"* AND "cabin"* AND "co2"* AND "headache"*'
    )
    # Quotes, operators and symbols typed by the crew cannot break the search.
    assert build_match_query('bleed" OR NOT (cut)*') == '"bleed"* AND "or"* AND "not"* AND "cut"*'
    assert build_match_query("  ?? ") is None
    assert build_match_query("eye pain", mode="OR") == '"eye"* OR "pain"*'


def test_screen_14_example_search_finds_the_co2_protocol(conn) -> None:
    results = search_articles(conn, "elevated cabin co2 headache")
    assert results[0]["id"] == "wiki-co2-01"
    assert results[0]["drawer_code"] == "DRAWER B2"
    assert results[0]["steps"][0]["title_en"] == "Check Local Airflow"


def test_prefix_and_fallback_search(conn) -> None:
    assert [r["id"] for r in search_articles(conn, "bleed")] == ["wiki-bleeding-01"]
    # No article has every word, so the guide falls back to any of them.
    loose = [r["id"] for r in search_articles(conn, "bleeding headache")]
    assert {"wiki-bleeding-01", "wiki-co2-01"} <= set(loose)
    assert search_articles(conn, "zzzz") == []


def test_topic_filter_and_empty_query(conn) -> None:
    trauma = search_articles(conn, "", "Trauma & Burns")
    assert {r["id"] for r in trauma} == {"wiki-trauma-01", "wiki-bleeding-01"}
    assert all(r["drawer_code"] == "DRAWER B1" for r in trauma)
    assert len(search_articles(conn)) == 10
    assert search_articles(conn, "cut", "Medications") == []


def test_article_kit_and_emergency_index(conn) -> None:
    article = get_article(conn, "wiki-medication-01")
    assert article["source_en"].startswith("World Health Organization")
    assert len(article["steps"]) == 4
    assert get_article(conn, "missing") is None

    drawers = kit_drawers(conn)
    assert [d["code"] for d in drawers] == ["DRAWER A1", "DRAWER A2", "DRAWER B1", "DRAWER B2"]
    b2 = next(d for d in drawers if d["code"] == "DRAWER B2")
    assert b2["items"][0] == {"slot_code": "Slot B2-01",
                              "name_en": "Digital Acoustic Stethoscope",
                              "status_en": "Charged 100%"}

    index = emergency_index(conn)
    assert len(index) == 10 and all(i["escalation_en"] for i in index)


def test_old_plain_steps_still_render() -> None:
    assert normalize_steps('["Rest", {"title_en": "Drink", "detail_en": "400 mL"}]') == [
        {"title_en": "Rest", "detail_en": ""},
        {"title_en": "Drink", "detail_en": "400 mL"},
    ]
    assert normalize_steps("not json") == []


def test_api_endpoints(temp_db_path: Path) -> None:
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with TestClient(fastapi_app) as client:
        search = client.get("/api/v1/wiki/search", params={"q": "eye scan"})
        assert search.status_code == 200
        body = search.json()
        assert body["categories"][0] == "CO2 Exposure"
        assert body["results"][0]["id"] == "wiki-vision-01"

        assert client.get("/api/v1/wiki/articles/wiki-trauma-01").status_code == 200
        assert client.get("/api/v1/wiki/articles/nope").status_code == 404
        assert len(client.get("/api/v1/wiki/emergency-index").json()["items"]) == 10
        assert len(client.get("/api/v1/kit/drawers").json()["drawers"]) == 4
