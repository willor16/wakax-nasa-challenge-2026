"""Validation and search tests for the medical guide and kit seed (D3-06)."""

import base64
import json
import re
from pathlib import Path

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import open_connection
from app.services.wiki_seed import (
    REQUIRED_KEYS,
    STEP_KEYS,
    load_medical_kit,
    load_wiki_articles,
    read_articles,
    read_kit,
)
from db.seed import seed_database

# Restricted entities are stored encoded so the codebase never names them.
_RESTRICTED = [base64.b64decode(v).decode() for v in ("bmFzYQ==", "Y2hpbmE=", "Y2hpbmVzZQ==")]
# The team's research sources are cited by document title, never by agency name.
BANNED = re.compile(rf"\b({'|'.join(_RESTRICTED)})\b", re.IGNORECASE)
NON_ASCII = re.compile(r"[^\x00-\x7F]")

# Kit drawers and topic filters exactly as drawn on the Medical Guide screen (14).
FIGMA_DRAWERS = {"DRAWER A1", "DRAWER A2", "DRAWER B1", "DRAWER B2"}
FIGMA_CATEGORIES = {
    "CO2 Exposure",
    "Vision & Pressure",
    "Sleep & Fatigue",
    "Trauma & Burns",
    "Medications",
}


def _all_articles() -> list[dict]:
    return read_articles()


def test_guide_articles_have_required_fields() -> None:
    for article in read_articles():
        for key in REQUIRED_KEYS:
            assert article.get(key), f"{article.get('id')} missing {key}"
        assert article.get("source_en"), f"{article['id']} missing source"


def test_guide_articles_match_figma_drawers_and_filters() -> None:
    # The five core topics are always there; the guide may grow further topics.
    assert FIGMA_CATEGORIES <= {a["category_en"] for a in read_articles()}
    for article in _all_articles():
        assert article["drawer_code"] in FIGMA_DRAWERS, article["id"]


def test_steps_have_heading_and_detail() -> None:
    for article in _all_articles():
        steps = article["steps_json"]
        assert 3 <= len(steps) <= 5, article["id"]
        for step in steps:
            assert set(step) == set(STEP_KEYS), article["id"]
            assert all(isinstance(step[k], str) and step[k].strip() for k in STEP_KEYS)
            assert len(step["title_en"]) <= 32, step["title_en"]


def test_ids_are_unique_across_all_articles() -> None:
    ids = [a["id"] for a in _all_articles()]
    assert len(ids) == len(set(ids))


def test_guide_text_is_plain_english_without_banned_terms() -> None:
    text = json.dumps(read_articles(), ensure_ascii=False)
    assert not BANNED.search(text)
    assert not NON_ASCII.search(text)


def test_guide_covers_required_topics() -> None:
    categories = {a["category_en"] for a in _all_articles()}
    assert FIGMA_CATEGORIES <= categories


def test_load_is_idempotent_and_searchable(temp_db_path: Path) -> None:
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with open_connection(temp_db_path) as conn:
        # seed.py already loads the guide articles and the kit.
        assert conn.execute("SELECT COUNT(*) FROM wiki_articles").fetchone()[0] == 10
        assert load_wiki_articles(conn) == 0
        assert load_medical_kit(conn) == 0
        source = conn.execute(
            "SELECT source_en FROM wiki_articles WHERE id = 'wiki-trauma-01'"
        ).fetchone()[0]
        assert source.startswith("World Health Organization")
        rows = conn.execute(
            """
            SELECT a.id FROM wiki_articles_fts AS f
            JOIN wiki_articles AS a ON a.rowid = f.rowid
            WHERE wiki_articles_fts MATCH ?
            """,
            ("bleeding",),
        ).fetchall()
    assert [r["id"] for r in rows] == ["wiki-bleeding-01"]


def test_kit_matches_screen_14() -> None:
    kit = read_kit()
    assert {d["code"] for d in kit["drawers"]} == FIGMA_DRAWERS
    drawers = {d["code"] for d in kit["drawers"]}
    slots = [i["slot_code"] for i in kit["items"]]
    assert len(slots) == len(set(slots))
    assert all(i["drawer_code"] in drawers for i in kit["items"])
    b2 = [i["name_en"] for i in kit["items"] if i["drawer_code"] == "DRAWER B2"]
    assert b2[:3] == [
        "Digital Acoustic Stethoscope", "Handheld Capnograph", "Glucose & Urine Strips",
    ]
    text = json.dumps(kit, ensure_ascii=False)
    assert not BANNED.search(text) and not NON_ASCII.search(text)
