"""
Part 2 - Resume Parser API.

POST /upload-resume   (protected - requires a valid JWT)

Accepts a PDF or DOCX resume, runs the hybrid Regex + LangChain/Groq LLM
pipeline (app/services/{pdf_parser,docx_parser,regex_parser,llm_parser,
merge_parser}.py), stores the uploaded file + raw text + parsed JSON in
PostgreSQL, and returns the merged structured JSON.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import get_db
from app.models.models import ParsedResume as ParsedResumeRecord
from app.models.models import Resume, User
from app.models.schemas import ErrorResponse, ParseResumeResponse
from app.services.docx_parser import UnsupportedFileTypeError
from app.services.llm_parser import LLMExtractionError
from app.services.merge_parser import run_hybrid_parser
from app.services.pdf_parser import FileParsingError
from app.utils.security import get_current_user

logger = logging.getLogger("ai_career_companion.resume")
settings = get_settings()

router = APIRouter(tags=["Resume Parsing"])


@router.post(
    "/upload-resume",
    response_model=ParseResumeResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
    status_code=status.HTTP_201_CREATED,
    summary="Upload and parse a resume (PDF or DOCX) into structured JSON",
)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParseResumeResponse:
    # --- Validate extension -------------------------------------------------
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed types: {settings.allowed_extensions}",
        )

    # --- Read & validate size -------------------------------------------------
    file_bytes = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max upload size of {settings.max_upload_mb} MB.",
        )
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    # --- Persist the raw file to disk -----------------------------------------
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4()}{ext}"
    stored_path = upload_dir / stored_filename
    with open(stored_path, "wb") as f:
        f.write(file_bytes)

    # --- Run hybrid parsing pipeline (Regex + LangChain/Groq LLM) -------------
    try:
        raw_text, regex_data, llm_data, merged = run_hybrid_parser(filename, file_bytes)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileParsingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except LLMExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error while parsing resume")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while parsing the resume.",
        ) from exc

    # --- Persist resume + parsed JSON in PostgreSQL ----------------------------
    resume_row = Resume(
        user_id=current_user.id,
        filename=filename,
        file_type=ext,
        file_path=str(stored_path),
        raw_text=raw_text,
    )
    db.add(resume_row)
    db.flush()  # get resume_row.id before commit

    parsed_row = ParsedResumeRecord(
        resume_id=resume_row.id,
        parsed_json=merged.model_dump(mode="json"),
        regex_json=regex_data.model_dump(mode="json"),
        llm_json=llm_data.model_dump(mode="json"),
    )
    db.add(parsed_row)
    db.commit()
    db.refresh(resume_row)

    logger.info("Resume '%s' parsed and stored for user %s", filename, current_user.email)

    return ParseResumeResponse(resume_id=resume_row.id, filename=filename, data=merged)
