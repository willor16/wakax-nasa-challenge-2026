"""Load Dev 3 medical guide articles and the medical kit into the database (idempotent)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.config import BACKEND_DIR

SNAPSHOT_DIR = BACKEND_DIR / "db" / "seed_snapshots"
WIKI_GUIDE_PATH = SNAPSHOT_DIR / "wiki_medical_guide.json"
MEDICAL_KIT_PATH = SNAPSHOT_DIR / "medical_kit.json"

REQUIRED_KEYS = ("id", "category_en", "title_en", "drawer_code", "steps_json", "escalation_en")

# Each step is shown on the guide screen as a short heading plus one line of detail.
STEP_KEYS = ("title_en", "detail_en")


def read_articles(path: Path = WIKI_GUIDE_PATH) -> list[dict]:
    """Read and return the guide articles from the JSON seed file."""
    return json.loads(path.read_text(encoding="utf-8"))


def read_kit(path: Path = MEDICAL_KIT_PATH) -> dict:
    """Read the medical kit drawers and items from the JSON seed file."""
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_guide_schema(conn: sqlite3.Connection) -> None:
    """Add ``wiki_articles.source_en`` to databases created before it existed."""
    columns = {r[1] for r in conn.execute("PRAGMA table_info(wiki_articles)")}
    if "source_en" not in columns:
        conn.execute("ALTER TABLE wiki_articles ADD COLUMN source_en TEXT")


def load_wiki_articles(conn: sqlite3.Connection, path: Path = WIKI_GUIDE_PATH) -> int:
    """Insert missing guide articles. Returns how many rows were added."""
    ensure_guide_schema(conn)
    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    added = 0
    for article in read_articles(path):
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO wiki_articles (
                id, category_en, title_en, drawer_code, steps_json,
                escalation_en, source_en, created_at_utc, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article["id"],
                article["category_en"],
                article["title_en"],
                article["drawer_code"],
                json.dumps(article["steps_json"]),
                article["escalation_en"],
                article.get("source_en"),
                now_utc,
                now_utc,
            ),
        )
        added += cursor.rowcount
    return added


def load_medical_kit(conn: sqlite3.Connection, path: Path = MEDICAL_KIT_PATH) -> int:
    """Insert missing kit drawers and items. Returns how many items were added."""
    kit = read_kit(path)
    for drawer in kit["drawers"]:
        conn.execute(
            "INSERT OR IGNORE INTO kit_drawers (code, name_en, sort_order) VALUES (?, ?, ?)",
            (drawer["code"], drawer["name_en"], drawer["sort_order"]),
        )
    added = 0
    for item in kit["items"]:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO kit_items (
                id, drawer_code, slot_code, name_en, status_en, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (item["id"], item["drawer_code"], item["slot_code"], item["name_en"],
             item["status_en"], item["sort_order"]),
        )
        added += cursor.rowcount
    return added


def load_medical_guide(conn: sqlite3.Connection) -> dict[str, int]:
    """Seed entry point: Dev 3 guide articles plus the medical kit."""
    return {"articles": load_wiki_articles(conn), "kit_items": load_medical_kit(conn)}
