"""Medical guide and kit locator API (D3-06), feeding screen 14 (``/guide``).

Open without a session on purpose: in an emergency any crew member must reach
the protocols in one step. Nothing here is personal data.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.db import open_connection
from app.services.guide import (
    GUIDE_CATEGORIES,
    emergency_index,
    get_article,
    kit_drawers,
    search_articles,
)

router = APIRouter(prefix="/api/v1", tags=["guide"])


@router.get("/wiki/search")
def search_guide(
    q: Annotated[str, Query(max_length=200)] = "",
    category: Annotated[str | None, Query(max_length=60)] = None,
) -> dict:
    """Protocols matching the words and/or the topic filter, best match first."""
    with open_connection() as conn:
        results = search_articles(conn, q, category)
    return {"query": q, "category": category, "categories": list(GUIDE_CATEGORIES),
            "results": results}


@router.get("/wiki/emergency-index")
def get_emergency_index() -> dict:
    """When to call the physician, for every protocol."""
    with open_connection() as conn:
        return {"items": emergency_index(conn)}


@router.get("/wiki/articles/{article_id}")
def get_guide_article(article_id: str) -> dict:
    """One protocol, opened from a notification's "Open Medical Guide" link."""
    with open_connection() as conn:
        article = get_article(conn, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocol not found.")
    return article


@router.get("/kit/drawers")
def get_kit_drawers() -> dict:
    """Medical kit drawers and what each one holds."""
    with open_connection() as conn:
        return {"drawers": kit_drawers(conn)}
