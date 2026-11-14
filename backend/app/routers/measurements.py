"""Centralized biomedical measurement ingestion and metric catalog endpoints."""

import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.db import open_connection
from app.services.contracts import evaluate_alerts, update_streaks

router = APIRouter(prefix="/api/v1", tags=["measurements"])


class MeasurementItemIn(BaseModel):
    metric_key: str = Field(..., min_length=1, max_length=80)
    value_num: float
    payload_json: dict[str, Any] = Field(default_factory=dict)


class MeasurementBatchIn(BaseModel):
    crew_id: str = Field(..., min_length=1, max_length=32)
    mission_stage: Literal["LAUNCH", "MISSION", "RETURN"]
    source_type: Literal["MANUAL", "AUTO"] = "MANUAL"
    recorded_at_utc: str | None = None
    items: list[MeasurementItemIn] = Field(..., min_length=1, max_length=32)


@router.get("/metrics/catalog")
def get_metric_catalog(category: str | None = Query(default=None)) -> list[dict]:
    """Return clinical metric definitions and reference ranges."""
    with open_connection() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM metric_catalog WHERE category = ? ORDER BY metric_key ASC",
                (category.upper(),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM metric_catalog ORDER BY category ASC, metric_key ASC"
            ).fetchall()
    return [dict(r) for r in rows]


@router.get("/measurements")
def list_measurements(
    crew_id: str = Query(..., min_length=1),
    metric_key: str | None = Query(default=None),
    mission_stage: Literal["LAUNCH", "MISSION", "RETURN"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    """Return recent append-only measurements for a crew member."""
    clauses = ["crew_id = ?"]
    params: list[Any] = [crew_id]

    if metric_key:
        clauses.append("metric_key = ?")
        params.append(metric_key)
    if mission_stage:
        clauses.append("mission_stage = ?")
        params.append(mission_stage)

    params.append(limit)
    sql = f"""
        SELECT id, crew_id, metric_key, mission_stage, source_type,
               recorded_at_utc, value_num, payload_json
        FROM measurements
        WHERE {' AND '.join(clauses)}
        ORDER BY recorded_at_utc DESC, id DESC
        LIMIT ?
    """
    with open_connection() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]


@router.post("/measurements", status_code=status.HTTP_201_CREATED)
def ingest_measurements(body: MeasurementBatchIn) -> dict:
    """Validate and store append-only measurements, evaluate alerts, and update streaks."""
    recorded_at = body.recorded_at_utc or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    day_utc = recorded_at[:10]

    with open_connection() as conn:
        crew_exists = conn.execute(
            "SELECT id FROM crew_members WHERE id = ? AND is_active = 1",
            (body.crew_id,),
        ).fetchone()
        if crew_exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active crew member not found.",
            )

        keys = [item.metric_key for item in body.items]
        placeholders = ",".join("?" for _ in keys)
        catalog_rows = conn.execute(
            f"SELECT metric_key FROM metric_catalog WHERE metric_key IN ({placeholders})",
            tuple(keys),
        ).fetchall()
        valid_keys = {r["metric_key"] for r in catalog_rows}
        unknown_keys = [k for k in keys if k not in valid_keys]
        if unknown_keys:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown metric keys: {', '.join(unknown_keys)}",
            )

        inserted_ids: list[int] = []
        alerts_created: list[int] = []

        for item in body.items:
            cursor = conn.execute(
                """
                INSERT INTO measurements (
                    crew_id, metric_key, mission_stage, source_type,
                    recorded_at_utc, value_num, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    body.crew_id,
                    item.metric_key,
                    body.mission_stage,
                    body.source_type,
                    recorded_at,
                    item.value_num,
                    json.dumps(item.payload_json),
                ),
            )
            measurement_id = int(cursor.lastrowid)
            inserted_ids.append(measurement_id)
            alerts_created.extend(evaluate_alerts(conn, measurement_id))

        streak = update_streaks(conn, body.crew_id, day_utc)
        conn.commit()

    return {
        "inserted_ids": inserted_ids,
        "alerts_created": alerts_created,
        "streak": streak,
        "recorded_at_utc": recorded_at,
    }
