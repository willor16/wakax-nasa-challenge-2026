"""Heart and lung recordings: capture upload, playback and results."""

import sqlite3
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.auth_utils import CurrentCrew, ensure_crew_access
from app.deps import get_db_conn
from app.services.acoustic_review import refine_finding
from app.services.auscultation_service import (
    MAX_AUDIO_BYTES,
    build_auscultation_results,
    resolve_sample_audio,
    save_auscultation_sample,
    session_progress,
)

router = APIRouter(prefix="/api/v1", tags=["auscultation"])

DbConn = Annotated[sqlite3.Connection, Depends(get_db_conn)]
OrganType = Literal["CARDIAC", "PULMONARY"]
AnatomicalSite = Literal["aortic", "pulmonic", "tricuspid", "mitral",
                         "upper_left", "upper_right", "lower_left", "lower_right"]


@router.post("/auscultation/samples", status_code=status.HTTP_201_CREATED)
def create_auscultation_sample(
    conn: DbConn,
    claims: CurrentCrew,
    background: BackgroundTasks,
    organ_type: Annotated[OrganType, Form()],
    anatomical_site: Annotated[AnatomicalSite, Form()],
    cabin_noise_dba: Annotated[float, Form(ge=0, le=140)],
    sha256_hex: Annotated[str, Form(min_length=64, max_length=64)],
    audio_file: Annotated[UploadFile, File()],
    content_encoding: Annotated[Literal["identity", "gzip"], Form()] = "identity",
) -> dict:
    """Store one 30-second recording of the signed-in crew member.

    The answer (sound class, confidence, rate) comes back at once; when the recording
    is sent for physician review, the assisted interpretation is written in the background.
    """
    audio_bytes = audio_file.file.read(MAX_AUDIO_BYTES + 1)
    try:
        saved = save_auscultation_sample(
            conn, crew_id=claims["sub"], organ_type=organ_type, anatomical_site=anatomical_site,
            cabin_noise_dba=cabin_noise_dba, sha256_hex=sha256_hex, audio_bytes=audio_bytes,
            content_encoding=content_encoding,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if saved["finding_id"] and not saved["finding_repeated"]:
        background.add_task(refine_finding, saved["finding_id"])
    return saved


@router.get("/auscultation/progress")
def get_capture_progress(conn: DbConn, claims: CurrentCrew) -> dict:
    """Listening spots already saved today by the signed-in crew member."""
    return session_progress(conn, claims["sub"])


@router.get("/auscultation/samples/{sample_id}/audio")
def get_sample_audio(sample_id: int, conn: DbConn, claims: CurrentCrew) -> FileResponse:
    try:
        path, owner = resolve_sample_audio(conn, sample_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    ensure_crew_access(claims, owner)
    return FileResponse(path=path, media_type="audio/wav", filename=path.name)


@router.get("/auscultation/{crew_id}")
def get_auscultation_results(
    crew_id: str,
    conn: DbConn,
    claims: CurrentCrew,
    co2_period: Annotated[Literal["24h", "7d", "30d"], Query()] = "24h",
) -> dict:
    ensure_crew_access(claims, crew_id)
    results = build_auscultation_results(conn, crew_id, co2_period)
    if results is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crew member not found.")
    return results
