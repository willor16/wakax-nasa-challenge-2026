"""Medical guide search and kit locator (D3-06), fully on board.

Search uses the ``wiki_articles_fts`` full-text index. Every word typed by the
crew is matched as a prefix ("head" finds "headache"); results need all words,
and when nothing matches all of them the guide falls back to any of them so the
crew never sees an empty screen for a near miss.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from app.services.wiki_seed import ensure_guide_schema

# Topic filters drawn on screen 14, in display order.
GUIDE_CATEGORIES = (
    "CO2 Exposure",
    "Vision & Pressure",
    "Sleep & Fatigue",
    "Trauma & Burns",
    "Medications",
)
_WORD = re.compile(r"[A-Za-z0-9]+")
MAX_RESULTS = 20


def normalize_steps(raw: str) -> list[dict[str, str]]:
    """Steps as ``{title_en, detail_en}``; older rows stored plain sentences."""
    try:
        steps = json.loads(raw)
    except json.JSONDecodeError:
        return []
    result = []
    for step in steps:
        if isinstance(step, dict):
            result.append({"title_en": str(step.get("title_en", "")),
                           "detail_en": str(step.get("detail_en", ""))})
        elif isinstance(step, str) and step.strip():
            result.append({"title_en": step.strip(), "detail_en": ""})
    return result


def build_match_query(text: str, mode: str = "AND") -> str | None:
    """Turn free text into a safe full-text query of quoted prefix terms."""
    words = [w.lower() for w in _WORD.findall(text)][:12]
    if not words:
        return None
    return f" {mode} ".join(f'"{w}"*' for w in words)


def _article(row: Any) -> dict:
    return {
        "id": row["id"],
        "category_en": row["category_en"],
        "title_en": row["title_en"],
        "drawer_code": row["drawer_code"],
        "steps": normalize_steps(row["steps_json"]),
        "escalation_en": row["escalation_en"],
        "source_en": row["source_en"],
    }


def search_articles(conn: sqlite3.Connection, query: str = "",
                    category: str | None = None, loose: bool = True) -> list[dict]:
    """Articles matching the words and/or topic, best match first."""
    ensure_guide_schema(conn)
    category_sql = "AND a.category_en = ?" if category else ""
    category_args = [category] if category else []

    match = build_match_query(query)
    if match is None:
        rows = conn.execute(
            f"SELECT a.* FROM wiki_articles AS a WHERE 1 = 1 {category_sql}"
            " ORDER BY a.category_en, a.title_en LIMIT ?",
            (*category_args, MAX_RESULTS),
        ).fetchall()
        return [_article(r) for r in rows]

    sql = f"""
        SELECT a.* FROM wiki_articles_fts AS f
        JOIN wiki_articles AS a ON a.rowid = f.rowid
        WHERE wiki_articles_fts MATCH ? {category_sql}
        ORDER BY bm25(wiki_articles_fts, 10.0, 4.0, 1.0)
        LIMIT ?
    """
    rows = conn.execute(sql, (match, *category_args, MAX_RESULTS)).fetchall()
    if not rows and loose:
        loose_match = build_match_query(query, mode="OR")
        rows = conn.execute(sql, (loose_match, *category_args, MAX_RESULTS)).fetchall()
    return [_article(r) for r in rows]


def get_article(conn: sqlite3.Connection, article_id: str) -> dict | None:
    ensure_guide_schema(conn)
    row = conn.execute("SELECT * FROM wiki_articles WHERE id = ?", (article_id,)).fetchone()
    return _article(row) if row else None


def emergency_index(conn: sqlite3.Connection) -> list[dict]:
    """When to call the physician, for every protocol, grouped for quick reading."""
    rows = conn.execute(
        "SELECT id, category_en, title_en, drawer_code, escalation_en FROM wiki_articles"
        " ORDER BY category_en, title_en"
    ).fetchall()
    return [dict(r) for r in rows]


def kit_drawers(conn: sqlite3.Connection) -> list[dict]:
    """Drawers in display order, each with its items."""
    drawers = conn.execute(
        "SELECT code, name_en FROM kit_drawers ORDER BY sort_order, code"
    ).fetchall()
    items = conn.execute(
        "SELECT drawer_code, slot_code, name_en, status_en FROM kit_items"
        " ORDER BY drawer_code, sort_order, slot_code"
    ).fetchall()
    by_drawer: dict[str, list[dict]] = {}
    for item in items:
        by_drawer.setdefault(item["drawer_code"], []).append({
            "slot_code": item["slot_code"],
            "name_en": item["name_en"],
            "status_en": item["status_en"],
        })
    return [
        {"code": d["code"], "name_en": d["name_en"], "items": by_drawer.get(d["code"], [])}
        for d in drawers
    ]
