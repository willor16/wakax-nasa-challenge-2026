"""Load Dev 3 medical guide articles into ``wiki_articles`` (idempotent)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.config import BACKEND_DIR

WIKI_GUIDE_PATH = BACKEND_DIR / "db" / "seed_snapshots" / "wiki_medical_guide.json"

REQUIRED_KEYS = ("id", "category_en", "title_en", "drawer_code", "steps_json", "escalation_en")


def read_articles(path: Path = WIKI_GUIDE_PATH) -> list[dict]:
    """Read and return the guide articles from the JSON seed file."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_wiki_articles(conn: sqlite3.Connection, path: Path = WIKI_GUIDE_PATH) -> int:
    """Insert missing guide articles. Returns how many rows were added."""
    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    added = 0
    for article in read_articles(path):
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO wiki_articles (
                id, category_en, title_en, drawer_code, steps_json,
                escalation_en, created_at_utc, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article["id"],
                article["category_en"],
                article["title_en"],
                article["drawer_code"],
                json.dumps(article["steps_json"]),
                article["escalation_en"],
                now_utc,
                now_utc,
            ),
        )
        added += cursor.rowcount
    return added
