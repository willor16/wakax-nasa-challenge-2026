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

# Topic filters drawn on screen 14, in display order.
GUIDE_CATEGORIES = (
    "CO2 Exposure",
    "Vision & Pressure",
    "Sleep & Fatigue",
    "Trauma & Burns",
    "Medications",
)


def guide_categories(conn: sqlite3.Connection) -> list[str]:
    """Topic filters: the five core topics first, then any topic the guide has grown into."""
    extra = [r[0] for r in conn.execute(
        "SELECT DISTINCT category_en FROM wiki_articles ORDER BY category_en")]
    return [*GUIDE_CATEGORIES, *(c for c in extra if c not in GUIDE_CATEGORIES)]


_WORD = re.compile(r"[A-Za-z0-9]+")
MAX_RESULTS = 20
MAX_CATALOG = 200


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
        # Protocols promoted from a physician-reviewed finding started from the onboard
        # pattern scan, so the screen marks them as produced with assisted analysis.
        "assisted": row["source_diagnosis_id"] is not None,
        "origin": article_origin(row["id"], row["source_diagnosis_id"]),
        "mission_protocol": article_origin(row["id"], row["source_diagnosis_id"]) != "shipped",
        "updated_at_utc": row["updated_at_utc"],
    }


MISSION_PREFIX = "wiki-mission-"


def article_origin(article_id: str, source_diagnosis_id: Any) -> str:
    """Where a protocol came from: the shipped guide, a physician-validated case promoted
    from a finding, or a protocol the physician wrote during the mission."""
    if source_diagnosis_id is not None:
        return "mission_case"
    if article_id.startswith(MISSION_PREFIX):
        return "physician"
    return "shipped"


class ArticleError(ValueError):
    """The protocol cannot be saved (unknown drawer, unreadable text, not editable)."""


def _check_article(conn: sqlite3.Connection, data: dict) -> None:
    from app.services.llm import screen_text_issues

    drawer = conn.execute("SELECT 1 FROM kit_drawers WHERE code = ?", (data["drawer_code"],))
    if drawer.fetchone() is None:
        raise ArticleError("Choose a drawer from the medical kit.")
    text = " ".join([
        data["title_en"], data["category_en"], data["escalation_en"],
        *(f"{s['title_en']} {s['detail_en']}" for s in data["steps"]),
    ])
    issues = screen_text_issues(text)
    if issues:
        raise ArticleError(
            "Write the protocol in plain English without technical terms (" + ", ".join(issues)
            + ")."
        )


def create_mission_article(conn: sqlite3.Connection, data: dict, author: str,
                           stamp: str) -> dict:
    """A protocol the crew physician validated during the mission; indexed for search at
    once by the full-text triggers."""
    _check_article(conn, data)
    count = conn.execute(
        "SELECT COUNT(*) FROM wiki_articles WHERE id LIKE ?", (f"{MISSION_PREFIX}%",)
    ).fetchone()[0]
    article_id = f"{MISSION_PREFIX}{count + 1:02d}"
    while conn.execute("SELECT 1 FROM wiki_articles WHERE id = ?", (article_id,)).fetchone():
        count += 1
        article_id = f"{MISSION_PREFIX}{count + 1:02d}"
    conn.execute(
        """INSERT INTO wiki_articles (id, category_en, title_en, drawer_code, steps_json,
           escalation_en, source_diagnosis_id, created_at_utc, updated_at_utc, source_en)
           VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)""",
        (article_id, data["category_en"], data["title_en"], data["drawer_code"],
         json.dumps(data["steps"]), data["escalation_en"], stamp, stamp,
         f"Mission protocol by {author} ({stamp[:10]})"),
    )
    return get_article(conn, article_id)  # type: ignore[return-value]


def update_mission_article(conn: sqlite3.Connection, article_id: str, data: dict,
                           author: str, stamp: str) -> dict:
    """Update a protocol written or validated during the mission; shipped ones never change."""
    current = get_article(conn, article_id)
    if current is None:
        raise LookupError(article_id)
    if not current["mission_protocol"]:
        raise ArticleError("Shipped protocols cannot be changed on board.")
    _check_article(conn, data)
    source = (current["source_en"] if current["origin"] == "mission_case"
              else f"Mission protocol by {author} (updated {stamp[:10]})")
    conn.execute(
        """UPDATE wiki_articles SET category_en = ?, title_en = ?, drawer_code = ?,
           steps_json = ?, escalation_en = ?, updated_at_utc = ?, source_en = ? WHERE id = ?""",
        (data["category_en"], data["title_en"], data["drawer_code"], json.dumps(data["steps"]),
         data["escalation_en"], stamp, source, article_id),
    )
    return get_article(conn, article_id)  # type: ignore[return-value]


def search_articles(conn: sqlite3.Connection, query: str = "",
                    category: str | None = None, loose: bool = True) -> list[dict]:
    """Articles matching the words and/or topic, best match first."""
    category_sql = "AND a.category_en = ?" if category else ""
    category_args = [category] if category else []

    match = build_match_query(query)
    if match is None:
        rows = conn.execute(
            f"SELECT a.* FROM wiki_articles AS a WHERE 1 = 1 {category_sql}"
            " ORDER BY a.source_diagnosis_id IS NULL AND a.id NOT LIKE 'wiki-mission-%',"
            " a.category_en, a.title_en LIMIT ?",
            (*category_args, MAX_CATALOG),
        ).fetchall()
        return [_article(r) for r in rows]

    sql = f"""
        SELECT a.* FROM wiki_articles_fts AS f
        JOIN wiki_articles AS a ON a.rowid = f.rowid
        WHERE wiki_articles_fts MATCH ? {category_sql}
        ORDER BY bm25(wiki_articles_fts, 10.0, 4.0, 1.0, 2.0)
        LIMIT ?
    """
    rows = conn.execute(sql, (match, *category_args, MAX_RESULTS)).fetchall()
    if not rows and loose:
        loose_match = build_match_query(query, mode="OR")
        rows = conn.execute(sql, (loose_match, *category_args, MAX_RESULTS)).fetchall()
    return [_article(r) for r in rows]


def get_article(conn: sqlite3.Connection, article_id: str) -> dict | None:
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
