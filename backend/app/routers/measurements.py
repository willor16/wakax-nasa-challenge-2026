import json
import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import get_db_conn
from app.schemas.measurements import (
    MeasurementBatchIn,
    MeasurementIngestOut,
    MeasurementRowOut,
    MeasurementSource,
    MetricCatalogItem,
    MissionStage,
    StreakUpdateSummary,
    normalize_utc_timestamp,
)
from app.services.contracts import evaluate_alerts, update_streaks

router = APIRouter(prefix="/api/v1", tags=["measurements"])

DbConn = Annotated[sqlite3.Connection, Depends(get_db_conn)]
HTTP_422_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


def _fetch_catalog(conn: sqlite3.Connection, category: str | None) -> list[MetricCatalogItem]:
    if category:
        rows = conn.execute(
            "SELECT * FROM metric_catalog WHERE category = ? ORDER BY metric_key ASC",
            (category.upper(),),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM metric_catalog ORDER BY category ASC, metric_key ASC"
        ).fetchall()
    return [MetricCatalogItem(**dict(r)) for r in rows]


@router.get("/metrics/catalog", response_model=list[MetricCatalogItem])
def get_metric_catalog(
    conn: DbConn,
    category: Annotated[str | None, Query()] = None,
) -> list[MetricCatalogItem]:
    return _fetch_catalog(conn, category)


@router.get("/metrics", response_model=list[MetricCatalogItem])
def list_metrics(
    conn: DbConn,
    category: Annotated[str | None, Query()] = None,
) -> list[MetricCatalogItem]:
    return _fetch_catalog(conn, category)


@router.get("/measurements", response_model=list[MeasurementRowOut])
def list_measurements(
    conn: DbConn,
    crew_id: Annotated[str, Query(min_length=1)],
    metric_key: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    mission_stage: Annotated[MissionStage | None, Query()] = None,
    source_type: Annotated[MeasurementSource | None, Query()] = None,
    from_utc: Annotated[str | None, Query()] = None,
    to_utc: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MeasurementRowOut]:
    clauses = ["m.crew_id = ?"]
    params: list[Any] = [crew_id.strip()]

    if metric_key:
        clauses.append("m.metric_key = ?")
        params.append(metric_key.strip())
    if category:
        clauses.append("c.category = ?")
        params.append(category.upper())
    if mission_stage:
        clauses.append("m.mission_stage = ?")
        params.append(mission_stage)
    if source_type:
        clauses.append("m.source_type = ?")
        params.append(source_type)
    if from_utc:
        try:
            clauses.append("m.recorded_at_utc >= ?")
            params.append(normalize_utc_timestamp(from_utc))
        except ValueError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE,
                detail=f"Invalid from_utc timestamp: {from_utc}",
            ) from exc
    if to_utc:
        try:
            clauses.append("m.recorded_at_utc <= ?")
            params.append(normalize_utc_timestamp(to_utc))
        except ValueError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE,
                detail=f"Invalid to_utc timestamp: {to_utc}",
            ) from exc

    params.extend([limit, offset])
    sql = f"""
        SELECT m.id, m.crew_id, m.metric_key, m.mission_stage, m.source_type,
               m.recorded_at_utc, m.value_num, m.payload_json
        FROM measurements AS m
        JOIN metric_catalog AS c ON c.metric_key = m.metric_key
        WHERE {' AND '.join(clauses)}
        ORDER BY m.recorded_at_utc DESC, m.id DESC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [MeasurementRowOut(**dict(r)) for r in rows]


def _ingest_batch(body: MeasurementBatchIn, conn: sqlite3.Connection) -> MeasurementIngestOut:
    recorded_at = body.recorded_at_utc or normalize_utc_timestamp(None)
    day_utc = recorded_at[:10]

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
            status_code=HTTP_422_UNPROCESSABLE,
            detail=f"Unknown metric keys: {', '.join(unknown_keys)}",
        )

    inserted_ids: list[int] = []
    alerts_created: list[int] = []

    for item in body.items:
        try:
            serialized_payload = json.dumps(item.payload_json, allow_nan=False)
        except ValueError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE,
                detail="Measurement payload_json must not contain NaN or Infinity values.",
            ) from exc

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
                serialized_payload,
            ),
        )
        measurement_id = int(cursor.lastrowid)
        inserted_ids.append(measurement_id)
        alerts_created.extend(evaluate_alerts(conn, measurement_id))

    streak = update_streaks(conn, body.crew_id, day_utc)
    return MeasurementIngestOut(
        inserted_ids=inserted_ids,
        alerts_created=alerts_created,
        streak=StreakUpdateSummary(**streak),
        recorded_at_utc=recorded_at,
    )


@router.post(
    "/measurements",
    response_model=MeasurementIngestOut,
    status_code=status.HTTP_201_CREATED,
)
def ingest_measurements(
    body: MeasurementBatchIn,
    conn: DbConn,
) -> MeasurementIngestOut:
    return _ingest_batch(body, conn)


@router.post(
    "/measurements/batch",
    response_model=MeasurementIngestOut,
    status_code=status.HTTP_201_CREATED,
)
def ingest_measurements_batch_alias(
    body: MeasurementBatchIn,
    conn: DbConn,
) -> MeasurementIngestOut:
    return _ingest_batch(body, conn)
