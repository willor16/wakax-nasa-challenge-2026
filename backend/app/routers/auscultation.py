import sqlite3
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.deps import get_db_conn
from app.schemas.auscultation import (
    AnatomicalSite,
    AuscultationResultsOut,
    AuscultationSampleCreatedOut,
    AuscultationStageFilter,
    MissionStageLiteral,
    OrganType,
)
from app.services.auscultation_service import (
    build_auscultation_results,
    resolve_sample_audio_path,
    save_auscultation_sample,
)

router = APIRouter(prefix="/api/v1", tags=["auscultation"])

DbConn = Annotated[sqlite3.Connection, Depends(get_db_conn)]


@router.post(
    "/auscultation/samples",
    response_model=AuscultationSampleCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
def create_auscultation_sample_endpoint(
    conn: DbConn,
    crew_id: Annotated[str, Form(min_length=2, max_length=32)],
    organ_type: Annotated[OrganType, Form()],
    anatomical_site: Annotated[AnatomicalSite, Form()],
    duration_sec: Annotated[int, Form()],
    cabin_noise_dba: Annotated[float, Form()],
    sha256_hex: Annotated[str, Form(min_length=64, max_length=64)],
    audio_file: Annotated[UploadFile, File()],
    mission_stage: Annotated[MissionStageLiteral, Form()] = "MISSION",
) -> AuscultationSampleCreatedOut:
    audio_bytes = audio_file.file.read()
    try:
        return save_auscultation_sample(
            conn=conn,
            crew_id=crew_id,
            mission_stage=mission_stage,
            organ_type=organ_type,
            anatomical_site=anatomical_site,
            duration_sec=duration_sec,
            cabin_noise_dba=cabin_noise_dba,
            sha256_hex=sha256_hex,
            audio_bytes=audio_bytes,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get("/auscultation/samples/{sample_id}/audio")
def stream_auscultation_sample_audio_endpoint(
    sample_id: int,
    conn: DbConn,
) -> FileResponse:
    try:
        audio_path = resolve_sample_audio_path(conn, sample_id=sample_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return FileResponse(
        path=audio_path,
        media_type="audio/webm",
        filename=audio_path.name,
    )


@router.get("/auscultation/{crew_id}", response_model=AuscultationResultsOut)
def get_auscultation_results_endpoint(
    crew_id: str,
    conn: DbConn,
    stage: Annotated[AuscultationStageFilter, Query()] = "ALL",
) -> AuscultationResultsOut:
    results = build_auscultation_results(conn, crew_id=crew_id, stage=stage)
    if results is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crew member '{crew_id}' was not found.",
        )
    return results
