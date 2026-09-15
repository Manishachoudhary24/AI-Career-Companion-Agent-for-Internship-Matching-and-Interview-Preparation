"""
AI Interview Preparation Agent API.

POST   /interview-prep/sessions                          - start a new preparation session
GET    /interview-prep/sessions                          - list the current user's sessions
GET    /interview-prep/sessions/{session_id}/messages     - list a session's messages
POST   /interview-prep/sessions/{session_id}/messages     - send a message, get an AI reply
POST   /interview-prep/sessions/{session_id}/document     - upload a PDF/DOCX for document-based Q&A
DELETE /interview-prep/sessions/{session_id}              - delete a session
GET    /interview-prep/context                            - resume-context-loaded indicator

This is a NEW, separate agent from the existing AI Assistant / Product
Chatbot (see app/routers/chat.py) - different tables (InterviewPrepSession /
InterviewPrepMessage), different system prompt, different purpose. It reuses:
  - The existing extracted resume data (ParsedResume.parsed_json), produced
    by the existing hybrid Regex + LLM resume parser - no resume parsing is
    duplicated here.
  - The existing PDF/DOCX text extractors (app/services/docx_parser.py,
    app/services/pdf_parser.py) for uploaded documents - no new parser.
  - The existing Groq LLM configuration.

Every endpoint requires authentication and verifies the session belongs to
the requesting user (404, not 403, for someone else's session - same
ownership pattern used elsewhere in this project).
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import get_db
from app.models.models import InterviewPrepMessage, InterviewPrepSession, Resume, User
from app.models.schemas import (
    ErrorResponse,
    InterviewPrepContextResponse,
    InterviewPrepDocumentUploadResponse,
    InterviewPrepMessageCreate,
    InterviewPrepMessageResponse,
    InterviewPrepSendResponse,
    InterviewPrepSessionCreate,
    InterviewPrepSessionResponse,
)
from app.services.docx_parser import UnsupportedFileTypeError, extract_text
from app.services.interview_prep_service import (
    InterviewPrepServiceError,
    default_session_title,
    generate_reply,
    get_latest_parsed_resume,
)
from app.services.pdf_parser import FileParsingError
from app.utils.security import get_current_user

from fastapi import Query

logger = logging.getLogger("ai_career_companion.interview_prep_router")
settings = get_settings()

router = APIRouter(prefix="/interview-prep", tags=["Interview Preparation Agent"])


def _get_owned_session(session_id: uuid.UUID, user: User, db: Session) -> InterviewPrepSession:
    session = db.query(InterviewPrepSession).filter(InterviewPrepSession.id == session_id).first()
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preparation session not found.")
    return session


def _to_session_response(session: InterviewPrepSession) -> InterviewPrepSessionResponse:
    return InterviewPrepSessionResponse(
        id=session.id,
        title=session.title,
        resume_id=session.resume_id,
        document_filename=session.document_filename,
        has_document=bool(session.document_text),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get(
    "/context",
    response_model=InterviewPrepContextResponse,
    summary="Resume-context-loaded indicator for the Interview Preparation page",
)
def get_context(
    resume_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InterviewPrepContextResponse:
    if resume_id:
        resume_row = (
            db.query(Resume)
            .filter(
                Resume.id == resume_id,
                Resume.user_id == current_user.id,
            )
            .first()
        )

        if resume_row is None or resume_row.parsed_resume is None:
            raise HTTPException(
                status_code=404,
                detail="Selected parsed resume was not found."
           )
    else:
        resume_row = get_latest_parsed_resume(db, current_user)
    
    
    if resume_row is None or resume_row.parsed_resume is None:
        return InterviewPrepContextResponse(resume_loaded=False)

    parsed = resume_row.parsed_resume.parsed_json or {}
    skills = [str(s) for s in (parsed.get("skills") or [])][:10]

    return InterviewPrepContextResponse(
        resume_loaded=True,
        resume_id=resume_row.id,
        filename=resume_row.filename,
        name=parsed.get("name"),
        current_job_title=parsed.get("current_job_title"),
        top_skills=skills,
        education_count=len(parsed.get("education") or []),
        experience_count=len(parsed.get("work_experience") or []),
        project_count=len(parsed.get("projects") or []),
    )


@router.post(
    "/sessions",
    response_model=InterviewPrepSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new Interview Preparation session",
)
def create_session(
    payload: InterviewPrepSessionCreate | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InterviewPrepSessionResponse:
    
    resume_row = None

    if payload and payload.resume_id:
        resume_row = (
            db.query(Resume)
            .filter(
                Resume.id == payload.resume_id,
                Resume.user_id == current_user.id,
            )
            .first()
        )

        if resume_row is None or resume_row.parsed_resume is None:
            raise HTTPException(
                status_code=404,
                detail="Selected parsed resume was not found."
            )
    else:
        resume_row = get_latest_parsed_resume(db, current_user)

    session = InterviewPrepSession(
        user_id=current_user.id,
        title=(payload.title if payload and payload.title else "New preparation"),
        resume_id=resume_row.id if resume_row else None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _to_session_response(session)


@router.get(
    "/sessions",
    response_model=list[InterviewPrepSessionResponse],
    summary="List the current user's Interview Preparation sessions",
)
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InterviewPrepSessionResponse]:
    rows = (
        db.query(InterviewPrepSession)
        .filter(InterviewPrepSession.user_id == current_user.id)
        .order_by(InterviewPrepSession.updated_at.desc())
        .all()
    )
    return [_to_session_response(s) for s in rows]


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a preparation session and its messages",
)
def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    session = _get_owned_session(session_id, current_user, db)
    db.delete(session)
    db.commit()


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[InterviewPrepMessageResponse],
    summary="List a preparation session's messages",
)
def list_messages(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InterviewPrepMessage]:
    _get_owned_session(session_id, current_user, db)
    return (
        db.query(InterviewPrepMessage)
        .filter(InterviewPrepMessage.session_id == session_id)
        .order_by(InterviewPrepMessage.created_at.asc())
        .all()
    )


@router.post(
    "/sessions/{session_id}/document",
    response_model=InterviewPrepDocumentUploadResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Upload a PDF/DOCX document for this session's document-based Q&A",
)
async def upload_document(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InterviewPrepDocumentUploadResponse:
    session = _get_owned_session(session_id, current_user, db)

    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed types: {settings.allowed_extensions}",
        )

    file_bytes = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max upload size of {settings.max_upload_mb} MB.",
        )
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    # Reuse the EXISTING PDF/DOCX extractors (same ones used by resume
    # parsing) - no duplicate parser is introduced for this feature.
    try:
        text = extract_text(filename, file_bytes)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileParsingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error while extracting document text")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while reading the document.",
        ) from exc

    session.document_filename = filename
    session.document_text = text
    db.commit()

    logger.info("Document '%s' attached to interview-prep session %s", filename, session.id)

    return InterviewPrepDocumentUploadResponse(
        session_id=session.id,
        filename=filename,
        characters_extracted=len(text),
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=InterviewPrepSendResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Send a message to the Interview Preparation Agent and get a reply",
)
def send_message(
    session_id: uuid.UUID,
    payload: InterviewPrepMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InterviewPrepSendResponse:
    session = _get_owned_session(session_id, current_user, db)

    text = (payload.message or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty.")

    user_msg = InterviewPrepMessage(
        session_id=session.id,
        user_id=current_user.id,
        role="user",
        message=text,
    )
    db.add(user_msg)
    db.flush()

    try:
        answer = generate_reply(db, session, current_user, text)
    except InterviewPrepServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Unexpected Interview Preparation Agent failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The Interview Preparation Agent is temporarily unavailable. Please try again.",
        ) from exc

    assistant_msg = InterviewPrepMessage(
        session_id=session.id,
        user_id=current_user.id,
        role="assistant",
        message=answer,
    )
    db.add(assistant_msg)

    if session.title == "New preparation":
        session.title = default_session_title(text)

    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)

    return InterviewPrepSendResponse(user_message=user_msg, assistant_message=assistant_msg)
