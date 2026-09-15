from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import get_db
from app.models.models import CoverLetter, ParsedResume as ParsedResumeRecord, Resume, User, UserProfile
from app.models.schemas import (
    CareerProfileResponse,
    CareerProfileUpdate,
    CoverLetterRequest,
    CoverLetterResponse,
    ParsedResumeSummary,
    ParseResumeResponse,
)
from app.services.internship_index import list_all_postings
from app.utils.security import get_current_user

logger = logging.getLogger("ai_career_companion.career")
router = APIRouter(tags=["Career Companion"])
settings = get_settings()

_PROFILE_LIST_FIELDS = ("education", "skills", "projects", "achievements", "experience", "custom_sections")


# ============================================================
# PROFILE HELPER
# ============================================================

def _get_or_create_profile(user: User, db: Session) -> UserProfile:
    record = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user.id)
        .first()
    )

    if not record:
        record = UserProfile(
            user_id=user.id,
            profile_json={
                "personal_details": {
                    "full_name": user.full_name,
                    "email": user.email,
                    "phone_number": user.phone_number,
                },
                "education": [],
                "skills": [],
                "projects": [],
                "achievements": [],
                "experience": [],
                "custom_sections": [],
            },
        )

        db.add(record)
        db.commit()
        db.refresh(record)

    return record


# ============================================================
# CAREER PROFILE - GET
# ============================================================

@router.get(
    "/career-profile",
    response_model=CareerProfileResponse,
)
def get_career_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the user's manually-maintained Career Profile as-is.

    IMPORTANT (see assignment section 3 - "Career Profile" requirement):
    this endpoint intentionally does NOT read from any parsed resume and
    does NOT auto-populate or merge parsed-resume data into the profile.
    The Career Profile is a separate, persistent, user-managed record;
    resume parsing (see /upload-resume and /parsed-resumes) is a distinct
    concept used only for internship matching and cover letters. The most
    recently uploaded resume's filename/date is still surfaced here (in
    the `resume` field) purely for display/navigation convenience - its
    contents are never copied into the profile fields below.
    """
    record = _get_or_create_profile(current_user, db)

    # Never modify the SQLAlchemy JSON object directly.
    # Make a copy so we don't accidentally mutate stored data.
    data = dict(record.profile_json or {})

    # --------------------------------------------------------
    # DEFAULT STRUCTURE (whatever the user has manually saved so far)
    # --------------------------------------------------------

    data.setdefault("personal_details", {})
    for field in _PROFILE_LIST_FIELDS:
        data.setdefault(field, [])

    # --------------------------------------------------------
    # LATEST RESUME - informational only, never merged into the
    # profile fields above.
    # --------------------------------------------------------

    latest = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.uploaded_at.desc())
        .first()
    )

    resume_info = None
    if latest is not None:
        resume_info = {
            "resume_id": str(latest.id),
            "filename": latest.filename,
            "uploaded_at": latest.uploaded_at,
            "is_parsed": latest.parsed_resume is not None,
        }

    return CareerProfileResponse(
        personal_details=data.get("personal_details", {}),
        education=data.get("education", []),
        skills=data.get("skills", []),
        projects=data.get("projects", []),
        achievements=data.get("achievements", []),
        experience=data.get("experience", []),
        custom_sections=data.get("custom_sections", []),
        resume=resume_info,
        photo_url=(
            f"/profile/photo/{current_user.id}"
            if record.photo_path
            else None
        ),
    )


# ============================================================
# CAREER PROFILE - UPDATE
# ============================================================

@router.put(
    "/career-profile",
    response_model=CareerProfileResponse,
)
def update_career_profile(
    payload: CareerProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = _get_or_create_profile(current_user, db)

    data = payload.model_dump()

    # Make sure all expected fields exist.
    data.setdefault("personal_details", {})
    for field in _PROFILE_LIST_FIELDS:
        data.setdefault(field, [])

    record.profile_json = data

    # Update user table fields as well.
    personal_details = data.get("personal_details") or {}

    if personal_details.get("full_name"):
        current_user.full_name = personal_details["full_name"]

    if "phone_number" in personal_details:
        current_user.phone_number = personal_details.get("phone_number")

    db.commit()
    db.refresh(record)

    return get_career_profile(current_user, db)


# ============================================================
# PARSED RESUMES - list + re-parse
#
# Reuses the existing Resume / ParsedResume tables and the existing
# hybrid Regex + LLM parsing pipeline (app.services.merge_parser). No new
# resume storage is introduced - this is purely a history/management view
# over data that already exists from POST /upload-resume.
# ============================================================

@router.get(
    "/parsed-resumes",
    response_model=list[ParsedResumeSummary],
    summary="List every resume the user has uploaded, most recent first",
)
def list_parsed_resumes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resumes = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.uploaded_at.desc())
        .all()
    )

    return [
        ParsedResumeSummary(
            resume_id=r.id,
            filename=r.filename,
            file_type=r.file_type,
            uploaded_at=r.uploaded_at,
            is_parsed=r.parsed_resume is not None,
            is_latest=(i == 0),
        )
        for i, r in enumerate(resumes)
    ]


@router.post(
    "/parsed-resumes/{resume_id}/reparse",
    response_model=ParseResumeResponse,
    summary="Re-run the hybrid Regex + LLM parser on an already-uploaded resume",
)
def reparse_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(404, "Resume not found.")

    stored_path = Path(resume.file_path)
    if not stored_path.exists():
        raise HTTPException(404, "The stored resume file could not be found on the server.")

    from app.services.docx_parser import UnsupportedFileTypeError
    from app.services.llm_parser import LLMExtractionError
    from app.services.merge_parser import run_hybrid_parser
    from app.services.pdf_parser import FileParsingError

    file_bytes = stored_path.read_bytes()

    try:
        raw_text, regex_data, llm_data, merged = run_hybrid_parser(resume.filename, file_bytes)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileParsingError as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMExtractionError as exc:
        raise HTTPException(502, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error while re-parsing resume")
        raise HTTPException(500, "An unexpected error occurred while re-parsing the resume.") from exc

    resume.raw_text = raw_text

    existing = (
        db.query(ParsedResumeRecord)
        .filter(ParsedResumeRecord.resume_id == resume.id)
        .first()
    )
    if existing:
        existing.parsed_json = merged.model_dump(mode="json")
        existing.regex_json = regex_data.model_dump(mode="json")
        existing.llm_json = llm_data.model_dump(mode="json")
    else:
        db.add(ParsedResumeRecord(
            resume_id=resume.id,
            parsed_json=merged.model_dump(mode="json"),
            regex_json=regex_data.model_dump(mode="json"),
            llm_json=llm_data.model_dump(mode="json"),
        ))

    db.commit()
    db.refresh(resume)

    return ParseResumeResponse(resume_id=resume.id, filename=resume.filename, data=merged)


# ============================================================
# PROFILE PHOTO - UPLOAD
# ============================================================

@router.post("/profile/photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower()

    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(
            400,
            "Only PNG, JPG, JPEG or WEBP images are supported.",
        )

    folder = Path("profile_photos")
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / f"{current_user.id}{ext}"

    path.write_bytes(await file.read())

    record = _get_or_create_profile(current_user, db)
    record.photo_path = str(path)

    db.commit()

    return {
        "message": "Profile photo updated.",
        "photo_url": f"/profile/photo/{current_user.id}",
    }


# ============================================================
# PROFILE PHOTO - GET
# ============================================================

@router.get("/profile/photo/{user_id}")
def get_profile_photo(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse

    record = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user_id)
        .first()
    )

    if (
        not record
        or not record.photo_path
        or not Path(record.photo_path).exists()
    ):
        raise HTTPException(
            404,
            "Profile photo not found.",
        )

    return FileResponse(record.photo_path)


# ============================================================
# COVER LETTER GENERATION
# ============================================================

@router.post(
    "/cover-letter/generate",
    response_model=CoverLetterResponse,
)
def generate_cover_letter(
    payload: CoverLetterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = (
        db.query(Resume)
        .filter(
            Resume.id == payload.resume_id,
            Resume.user_id == current_user.id,
        )
        .first()
    )

    if not resume or not resume.parsed_resume:
        raise HTTPException(
            404,
            "Parsed resume not found.",
        )

    internship = next(
        (
            x
            for x in list_all_postings()
            if x["id"] == payload.internship_id
        ),
        None,
    )

    if not internship:
        raise HTTPException(
            404,
            "Internship not found.",
        )

    parsed = resume.parsed_resume.parsed_json or {}

    prompt = f"""
Write a professional, concise internship cover letter using ONLY
the candidate and internship data below.

Do not invent skills, experience, projects, achievements, dates,
or company facts.

Candidate:
{json.dumps(parsed, ensure_ascii=False)}

Internship:
{json.dumps(internship, ensure_ascii=False)}

Return only the cover letter, with greeting and sign-off.
"""

    try:
        from groq import Groq

        client = Groq(
            api_key=settings.groq_api_key
        )

        result = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a careful career-writing assistant. "
                        "Use only supplied facts."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.3,
        )

        content = (
            result.choices[0].message.content or ""
        ).strip()

        if not content:
            raise HTTPException(
                502,
                "Cover letter generation returned an empty response.",
            )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            502,
            f"Cover letter generation failed: {exc}",
        ) from exc

    letter = CoverLetter(
        user_id=current_user.id,
        internship_id=internship["id"],
        internship_role=internship["role_title"],
        company=internship["company"],
        content=content,
    )

    db.add(letter)
    db.commit()
    db.refresh(letter)

    return letter


# ============================================================
# COVER LETTERS - LIST
# ============================================================

@router.get(
    "/cover-letters",
    response_model=list[CoverLetterResponse],
)
def list_cover_letters(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(CoverLetter)
        .filter(CoverLetter.user_id == current_user.id)
        .order_by(CoverLetter.created_at.desc())
        .all()
    )
    
    
 # delete a parsed resume
@router.delete(
    "/parsed-resumes/{resume_id}",
    status_code=status.HTTP_200_OK,
)
def delete_parsed_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == current_user.id,
        )
        .first()
    )

    if resume is None:
        raise HTTPException(404, "Resume not found.")

    stored_path = Path(resume.file_path)

    db.delete(resume)
    db.commit()

    if stored_path.exists():
        try:
            stored_path.unlink()
        except OSError:
            pass

    return {"message": "Resume deleted successfully."}