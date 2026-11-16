"""Medical guide and kit locator API (D3-06), feeding screen 14 (``/guide``).

Open without a session on purpose: in an emergency any crew member must reach
the protocols in one step. Nothing here is personal data.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth_utils import PhysicianCrew
from app.db import open_connection
from app.services.guide import (
    ArticleError,
    create_mission_article,
    emergency_index,
    get_article,
    guide_categories,
    kit_drawers,
    search_articles,
    update_mission_article,
)
from app.services.mission_clock import to_iso, utc_now

router = APIRouter(prefix="/api/v1", tags=["guide"])


class StepIn(BaseModel):
    title_en: str = Field(min_length=3, max_length=32)
    detail_en: str = Field(min_length=5, max_length=220)


class WikiArticleIn(BaseModel):
    """A protocol validated by the crew physician during the mission."""

    title_en: str = Field(min_length=5, max_length=120)
    category_en: str = Field(min_length=3, max_length=40)
    drawer_code: str = Field(min_length=3, max_length=20)
    steps: list[StepIn] = Field(min_length=3, max_length=5)
    escalation_en: str = Field(min_length=10, max_length=300)

    def as_data(self) -> dict:
        data = self.model_dump()
        for key in ("title_en", "category_en", "drawer_code", "escalation_en"):
            data[key] = " ".join(data[key].split())
        data["steps"] = [{k: " ".join(v.split()) for k, v in step.items()}
                         for step in data["steps"]]
        return data


def _author(conn, crew_id: str) -> str:
    row = conn.execute("SELECT full_name FROM crew_members WHERE id = ?", (crew_id,)).fetchone()
    return f"Dr. {row['full_name'].split()[-1]}" if row else "the crew physician"


@router.get("/wiki/search")
def search_guide(
    q: Annotated[str, Query(max_length=200)] = "",
    category: Annotated[str | None, Query(max_length=60)] = None,
) -> dict:
    """Protocols matching the words and/or the topic filter, best match first."""
    with open_connection() as conn:
        results = search_articles(conn, q, category)
        categories = guide_categories(conn)
    return {"query": q, "category": category, "categories": categories, "results": results}


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


@router.post("/wiki/articles", status_code=status.HTTP_201_CREATED)
def create_guide_article(body: WikiArticleIn, claims: PhysicianCrew) -> dict:
    """The crew physician adds a protocol validated during the mission."""
    with open_connection() as conn:
        try:
            return create_mission_article(conn, body.as_data(), _author(conn, claims["sub"]),
                                          to_iso(utc_now()))
        except ArticleError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error


@router.put("/wiki/articles/{article_id}")
def update_guide_article(article_id: str, body: WikiArticleIn, claims: PhysicianCrew) -> dict:
    """The crew physician updates a protocol written or validated during the mission."""
    with open_connection() as conn:
        try:
            return update_mission_article(conn, article_id, body.as_data(),
                                          _author(conn, claims["sub"]), to_iso(utc_now()))
        except LookupError as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Protocol not found.") from error
        except ArticleError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
