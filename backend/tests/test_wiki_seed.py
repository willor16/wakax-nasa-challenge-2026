"""Validation and FTS5 tests for the Dev 3 medical guide seed (D3-04 prep)."""

import base64
import json
import re
from pathlib import Path

from app.config import SCHEMA_PATH, SEED_SNAPSHOT_PATH
from app.db import open_connection
from app.services.wiki_seed import REQUIRED_KEYS, load_wiki_articles, read_articles
from db.seed import seed_database

# Restricted entities are stored encoded so the codebase never names them.
_RESTRICTED = [base64.b64decode(v).decode() for v in ("bmFzYQ==", "Y2hpbmE=", "Y2hpbmVzZQ==")]
BANNED = re.compile(rf"\b({'|'.join(_RESTRICTED)})\b", re.IGNORECASE)
NON_ASCII = re.compile(r"[^\x00-\x7F]")
DRAWER = re.compile(r"^DRAWER [A-Z]\d$")


def _all_articles() -> list[dict]:
    snapshot = json.loads(SEED_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return snapshot["wiki_articles"] + read_articles()


def test_guide_articles_have_required_fields() -> None:
    for article in read_articles():
        for key in REQUIRED_KEYS:
            assert article.get(key), f"{article.get('id')} missing {key}"
        assert article.get("source_en"), f"{article['id']} missing source"
        assert DRAWER.match(article["drawer_code"])
        assert 3 <= len(article["steps_json"]) <= 8
        assert all(isinstance(step, str) and step.strip() for step in article["steps_json"])


def test_ids_and_drawers_are_unique_across_all_articles() -> None:
    articles = _all_articles()
    ids = [a["id"] for a in articles]
    drawers = [a["drawer_code"] for a in articles]
    assert len(ids) == len(set(ids))
    assert len(drawers) == len(set(drawers))


def test_guide_text_is_plain_english_without_banned_terms() -> None:
    text = json.dumps(read_articles(), ensure_ascii=False)
    assert not BANNED.search(text)
    assert not NON_ASCII.search(text)


def test_guide_covers_required_topics() -> None:
    categories = {a["category_en"] for a in _all_articles()}
    for topic in ("CO2 Exposure", "Vision & Pressure", "Sleep & Fatigue", "Trauma", "Medication"):
        assert topic in categories


def test_load_is_idempotent_and_searchable(temp_db_path: Path) -> None:
    seed_database(db_path=temp_db_path, schema_path=SCHEMA_PATH, snapshot_path=SEED_SNAPSHOT_PATH)
    with open_connection(temp_db_path) as conn:
        assert load_wiki_articles(conn) == 3
        assert load_wiki_articles(conn) == 0
        rows = conn.execute(
            """
            SELECT a.id FROM wiki_articles_fts AS f
            JOIN wiki_articles AS a ON a.rowid = f.rowid
            WHERE wiki_articles_fts MATCH ?
            """,
            ("bleeding",),
        ).fetchall()
    assert [r["id"] for r in rows] == ["wiki-bleeding-01"]
