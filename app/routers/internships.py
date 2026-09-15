"""
Part 3 - Internship Matching API (Milestone 2 RAG pipeline).

GET /internships/                    -> browse the synthetic catalog (public)
GET /internships/match/{resume_id}   -> RAG-match a parsed resume against it (protected)

Ties together:
  - Assignment 1's auth (app.utils.security.get_current_user) and resume
    storage (Resume + ParsedResume rows, produced by /upload-resume).
  - The Milestone 2 vector index / matcher, ported into
    app/services/internship_index.py and app/services/internship_matcher.py.
  - app/services/resume_profile.py, the adapter that bridges the two: it
    flattens ParsedResume.parsed_json into the shape the matcher expects.

A 404 (not a 403) is returned for a resume that exists but belongs to
someone else, so a caller can't distinguish "not found" from "not yours" -
same ownership-check pattern used elsewhere in this project.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import schemas
from app.models.database import get_db
from app.models.models import AppliedInternship, Resume, User
from app.services.internship_index import list_all_postings
from app.services.internship_matcher import match_resume_to_internships
from app.services.resume_profile import build_resume_match_profile
from app.utils.security import get_current_user

logger = logging.getLogger("ai_career_companion.internships")

router = APIRouter(prefix="/internships", tags=["Internship Matching"])


@router.get(
    "/",
    response_model=list[schemas.InternshipPosting],
    summary="Browse the internship catalog",
)
def list_internships() -> list[dict]:
    """The full synthetic internship catalog (see app/data/internships.json).
    Static reference data, not tied to any user, so this is unauthenticated."""
    return list_all_postings()


@router.get(
    "/match/{resume_id}",
    response_model=schemas.InternshipMatchResponse,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        404: {"model": schemas.ErrorResponse},
    },
    summary="RAG-match a parsed resume against the internship catalog",
)
def match_internships(
    resume_id: uuid.UUID,
    k: int = Query(default=5, ge=1, le=20, description="Number of top matches to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> schemas.InternshipMatchResponse:
    """Runs the resume's parsed skills/education/projects through the FAISS
    index of internship postings and returns the top-k most similar ones,
    each with a skill-gap breakdown and (if Groq is configured) a short
    summary. Requires the resume to have already been parsed via
    POST /upload-resume."""
    resume = (
        db.query(Resume)
        .options(joinedload(Resume.parsed_resume))
        .filter(Resume.id == resume_id)
        .first()
    )
    if resume is None or resume.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    profile = build_resume_match_profile(resume)
    try:
        match_data = match_resume_to_internships(profile, k=k)
    except FileNotFoundError as exc:
        # Raised by internship_index.get_vectorstore() if the FAISS index
        # hasn't been built yet (e.g. auto-build failed at startup, most
        # likely due to no internet access to download the embedding model).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if not match_data["results"] and match_data["query_skills"] is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This resume has no usable skills, education, projects, or extracted text to match on.",
        )

    return schemas.InternshipMatchResponse(
        resume_id=resume_id,
        query_profile=profile.as_dict(),
        **match_data,
    )


# --------------------------------------------------------------------------- #
# Applied Internships - in-app "Apply Now" (no external redirect).
#
# A unique (user_id, internship_id) constraint on the applied_internships
# table (see app/models/models.py) is the source of truth that prevents
# duplicate applications; this endpoint also checks first so re-clicking
# "Apply Now" on an already-applied posting is a harmless no-op that
# returns the existing application instead of erroring.
# --------------------------------------------------------------------------- #


@router.post(
    "/{internship_id}/apply",
    response_model=schemas.AppliedInternshipResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": schemas.ErrorResponse}},
    summary="Apply to an internship (stored in-app, no external redirect)",
)
def apply_to_internship(
    internship_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppliedInternship:
    posting = next((p for p in list_all_postings() if p["id"] == internship_id), None)
    if posting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found.")

    existing = (
        db.query(AppliedInternship)
        .filter(
            AppliedInternship.user_id == current_user.id,
            AppliedInternship.internship_id == internship_id,
        )
        .first()
    )
    if existing:
        return existing

    application = AppliedInternship(
        user_id=current_user.id,
        internship_id=internship_id,
        role_title=posting["role_title"],
        company=posting["company"],
    )
    db.add(application)
    try:
        db.commit()
    except IntegrityError:
        # Race condition: another request applied first. Return that row.
        db.rollback()
        existing = (
            db.query(AppliedInternship)
            .filter(
                AppliedInternship.user_id == current_user.id,
                AppliedInternship.internship_id == internship_id,
            )
            .first()
        )
        if existing:
            return existing
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not record application.")

    db.refresh(application)
    return application


@router.get(
    "/applied/me",
    response_model=list[schemas.AppliedInternshipResponse],
    summary="List the current user's applied internships",
)
def list_my_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AppliedInternship]:
    return (
        db.query(AppliedInternship)
        .filter(AppliedInternship.user_id == current_user.id)
        .order_by(AppliedInternship.applied_at.desc())
        .all()
    )
