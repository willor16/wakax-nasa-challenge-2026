import json
import sqlite3
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth_utils import CurrentCrew, ensure_crew_access
from app.deps import get_db_conn
from app.schemas.measurements import (
    MeasurementBatchIn,
    MeasurementIngestOut,
    MeasurementRowOut,
    MeasurementSource,
    MetricCatalogItem,
    MissionStage,
    ParameterHelpItem,
    StreakUpdateSummary,
    normalize_utc_timestamp,
)
from app.services import reference_ranges
from app.services.contracts import evaluate_alerts, update_streaks
from app.services.mission_clock import current_stage, parse_iso, utc_now

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
    items = []
    for r in rows:
        entry = reference_ranges.metric(r["metric_key"]) or {}
        items.append(MetricCatalogItem(**dict(r), plausible_min=entry.get("plausible_min"),
                                       plausible_max=entry.get("plausible_max")))
    return items


@router.get("/metrics/catalog", response_model=list[MetricCatalogItem])
def get_metric_catalog(
    conn: DbConn,
    category: Annotated[str | None, Query()] = None,
) -> list[MetricCatalogItem]:
    return _fetch_catalog(conn, category)


@router.get("/metrics/help", response_model=list[ParameterHelpItem])
def get_parameter_help() -> list[ParameterHelpItem]:
    """What each parameter measures, how to read it and its mission impact (public text)."""
    return [ParameterHelpItem(**entry) for entry in reference_ranges.help_entries()]


@router.get("/metrics", response_model=list[MetricCatalogItem])
def list_metrics(
    conn: DbConn,
    category: Annotated[str | None, Query()] = None,
) -> list[MetricCatalogItem]:
    return _fetch_catalog(conn, category)


@router.get("/measurements", response_model=list[MeasurementRowOut])
def list_measurements(
    conn: DbConn,
    claims: CurrentCrew,
    crew_id: Annotated[str | None, Query()] = None,
    metric_key: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    mission_stage: Annotated[MissionStage | None, Query()] = None,
    source_type: Annotated[MeasurementSource | None, Query()] = None,
    from_utc: Annotated[str | None, Query()] = None,
    to_utc: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MeasurementRowOut]:
    target = (crew_id or "").strip() or claims["sub"]
    ensure_crew_access(claims, target)
    clauses = ["m.crew_id = ?"]
    params: list[Any] = [target]

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
                detail="The start date is not a valid date and time.",
            ) from exc
    if to_utc:
        try:
            clauses.append("m.recorded_at_utc <= ?")
            params.append(normalize_utc_timestamp(to_utc))
        except ValueError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE,
                detail="The end date is not a valid date and time.",
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


def _ingest_batch(body: MeasurementBatchIn, conn: sqlite3.Connection,
                  claims: dict[str, Any]) -> MeasurementIngestOut:
    crew_id = body.crew_id or claims["sub"]
    ensure_crew_access(claims, crew_id)
    recorded_at = body.recorded_at_utc or normalize_utc_timestamp(None)
    if parse_iso(recorded_at) > utc_now() + timedelta(minutes=5):
        raise HTTPException(HTTP_422_UNPROCESSABLE, "The reading time cannot be in the future.")
    day_utc = recorded_at[:10]

    crew_exists = conn.execute(
        "SELECT id FROM crew_members WHERE id = ? AND is_active = 1", (crew_id,)
    ).fetchone()
    if crew_exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")

    # The mission decides the stage; a client can no longer rewrite pre-flight baselines.
    stage = current_stage(conn)
    if body.mission_stage is not None and body.mission_stage != stage:
        raise HTTPException(
            HTTP_422_UNPROCESSABLE,
            f"The mission is in the {stage.title()} stage; readings are filed under it.",
        )

    keys = [item.metric_key for item in body.items]
    placeholders = ",".join("?" for _ in keys)
    catalog_rows = conn.execute(
        f"SELECT metric_key, display_name_en, unit FROM metric_catalog "
        f"WHERE metric_key IN ({placeholders})",
        tuple(keys),
    ).fetchall()
    catalog = {r["metric_key"]: r for r in catalog_rows}
    unknown_keys = [k for k in keys if k not in catalog]
    if unknown_keys:
        raise HTTPException(
            HTTP_422_UNPROCESSABLE,
            f"These readings are not part of the health catalog: {', '.join(unknown_keys)}",
        )
    for item in body.items:
        if not reference_ranges.is_plausible(item.metric_key, item.value_num):
            entry = reference_ranges.metric(item.metric_key) or {}
            name = catalog[item.metric_key]["display_name_en"]
            raise HTTPException(
                HTTP_422_UNPROCESSABLE,
                f"{name} of {item.value_num:g} {catalog[item.metric_key]['unit']} is not possible. "
                f"Enter a value between {entry.get('plausible_min'):g} and "
                f"{entry.get('plausible_max'):g}.",
            )

    inserted_ids: list[int] = []
    alerts_created: list[int] = []

    for item in body.items:
        try:
            serialized_payload = json.dumps(item.payload_json, allow_nan=False)
        except ValueError as exc:
            raise HTTPException(
                status_code=HTTP_422_UNPROCESSABLE,
                detail="Extra details may only contain ordinary numbers and text.",
            ) from exc

        cursor = conn.execute(
            """
            INSERT INTO measurements (
                crew_id, metric_key, mission_stage, source_type,
                recorded_at_utc, value_num, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                crew_id,
                item.metric_key,
                stage,
                body.source_type,
                recorded_at,
                item.value_num,
                serialized_payload,
            ),
        )
        measurement_id = int(cursor.lastrowid)
        inserted_ids.append(measurement_id)
        alerts_created.extend(evaluate_alerts(conn, measurement_id))

    streak = update_streaks(conn, crew_id, day_utc)
    return MeasurementIngestOut(
        inserted_ids=inserted_ids,
        alerts_created=alerts_created,
        mission_stage=stage,
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
    claims: CurrentCrew,
) -> MeasurementIngestOut:
    return _ingest_batch(body, conn, claims)


@router.post(
    "/measurements/batch",
    response_model=MeasurementIngestOut,
    status_code=status.HTTP_201_CREATED,
)
def ingest_measurements_batch_alias(
    body: MeasurementBatchIn,
    conn: DbConn,
    claims: CurrentCrew,
) -> MeasurementIngestOut:
    return _ingest_batch(body, conn, claims)
