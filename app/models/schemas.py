"""
Pydantic schemas.

Section 1 - Auth / User management request & response models.
Section 2 - Resume parsing models, ported directly from the original hybrid
            Regex + LLM resume-parser project (RegexExtraction / LLMExtraction
            / ParsedResume), so the parsing contract is unchanged.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional, Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
# --------------------------------------------------------------------------- #
# 1. Auth / User management
# --------------------------------------------------------------------------- #


class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    phone_number: Optional[str] = Field(None, max_length=50)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    phone_number: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=50)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    # NOTE: In production this token would be emailed to the user, never
    # returned in the API response. It is returned here only because this
    # project has no configured email/SMTP service (dev/demo convenience).
    reset_token: str
    expires_in_minutes: int


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class TokenData(BaseModel):
    user_id: Optional[str] = None
    jti: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    detail: Optional[str] = None


# --------------------------------------------------------------------------- #
# 2. Resume parsing (ported from the hybrid Regex + LLM resume parser)
# --------------------------------------------------------------------------- #


class RegexExtraction(BaseModel):
    """Fields that can be reliably extracted with pattern matching alone."""

    name: Optional[str] = Field(None, description="Best-effort name guess from regex/heuristics")
    emails: List[str] = Field(default_factory=list)
    phone_numbers: List[str] = Field(default_factory=list)
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio_website: Optional[str] = None
    twitter: Optional[str] = None


class Education(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    grade: Optional[str] = None
    location: Optional[str] = None


class WorkExperience(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = None
    responsibilities: List[str] = Field(default_factory=list)
    technologies_used: List[str] = Field(default_factory=list)


class Internship(BaseModel):
    role: Optional[str] = None
    organization: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_description(cls, value):
        if isinstance(value, dict):
            value = value.copy()

            if isinstance(value.get("description"), list):
                value["description"] = " ".join(
                    str(item) for item in value["description"]
                )

            # LLM may return company/title instead of organization/role
            if "company" in value and "organization" not in value:
                value["organization"] = value.pop("company")

            if "title" in value and "role" not in value:
                value["role"] = value.pop("title")

        return value


class Project(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    technologies_used: List[str] = Field(default_factory=list)
    link: Optional[str] = None
    duration: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_project(cls, value):
        if isinstance(value, dict):
            value = value.copy()

            # Convert description list → string
            if isinstance(value.get("description"), list):
                value["description"] = " ".join(
                    str(item) for item in value["description"]
                )

            # LLM may return "title" instead of "name"
            if "title" in value and "name" not in value:
                value["name"] = value.pop("title")

            # LLM may return "technologies" instead of "technologies_used"
            if "technologies" in value and "technologies_used" not in value:
                value["technologies_used"] = value.pop("technologies")

        return value


class Certification(BaseModel):
    name: Optional[str] = None
    issuing_organization: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    credential_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def convert_string(cls, value):
        if isinstance(value, str):

            # Example:
            # "Introduction to C programming - Solo learn"
            if " - " in value:
                name, organization = value.split(" - ", 1)

                return {
                    "name": name.strip(),
                    "issuing_organization": organization.strip(),
                    "issue_date": None,
                }

            # Example:
            # "Machine Learning Foundations, AWS Academy, 2026"
            parts = [p.strip() for p in value.split(",")]

            return {
                "name": parts[0] if parts else value,
                "issuing_organization": (
                    parts[1] if len(parts) > 1 else None
                ),
                "issue_date": (
                    parts[2] if len(parts) > 2 else None
                ),
            }

        return value


class Publication(BaseModel):
    title: Optional[str] = None
    publisher: Optional[str] = None
    date: Optional[str] = None
    link: Optional[str] = None
    description: Optional[str] = None


class LanguageProficiency(BaseModel):
    language: str
    proficiency: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def convert_string(cls, value):
        if isinstance(value, str):

            # Example:
            # "Kannada (Native)"
            if "(" in value and value.endswith(")"):
                name, proficiency = value.rsplit("(", 1)

                return {
                    "language": name.strip(),
                    "proficiency": proficiency[:-1].strip(),
                }

            # Example:
            # "Kannada"
            # "English"
            return {
                "language": value.strip(),
                "proficiency": None,
            }

        if isinstance(value, dict):
            value = value.copy()

            # Support alternate LLM format:
            # {"name": "Kannada"}
            if "name" in value and "language" not in value:
                value["language"] = value.pop("name")

        return value

class Achievement(BaseModel):
    name: str
    description: Optional[str] = None
    date: Optional[str] = None


class ContactDetails(BaseModel):
    """Contact info as understood contextually by the LLM (may overlap regex)."""

    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio_website: Optional[str] = None

class Skills(BaseModel):
    technical_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)

class LLMExtraction(BaseModel):
    """Everything the LLM is asked to infer from free-form resume text."""
    
    @model_validator(mode="before")
    @classmethod
    def normalize_llm_output(cls, value):
        if not isinstance(value, dict):
            return value
        
        value = value.copy()
        
        if "name" in value and "full_name" not in value:
            value["full_name"] = value.pop("name")
            
        contact = value.get("contact_details")
        if not isinstance(contact, dict):
            contact = {}
        
        if isinstance(value.get("contact_information"), dict):
            contact = {
                **contact,
                **value.pop("contact_information")
            }
            
        for source_key, target_key in [
            ("email", "email"),
            ("phone", "phone"),
            ("address", "address"),
            ("location", "address"),
            ("linkedin", "linkedin"),
            ("github", "github"),
            ("portfolio", "portfolio_website"),
            ("portfolio_website", "portfolio_website"),
        ]:    
            if source_key in value and value[source_key] is not None:
                if target_key not in contact:
                    contact[target_key] = value[source_key]

        value["contact_details"] = contact
        
        skills = value.get("skills")

        if isinstance(skills, dict):
            technical = skills.get("technical_skills") or []
            soft = skills.get("soft_skills") or []

            value["skills"] = [
                str(skill).strip()
                for skill in [*technical, *soft]
                if str(skill).strip()
            ]
            if not value.get("technical_skills"):
                value["technical_skills"] = technical

            if not value.get("soft_skills"):
                value["soft_skills"] = soft
                
        elif isinstance(skills, str):
            value["skills"] = [skills.strip()] if skills.strip() else []

        elif skills is None:
            technical = value.get("technical_skills") or []
            soft = value.get("soft_skills") or []

            value["skills"] = [
                str(skill).strip()
                for skill in [*technical, *soft]
                if str(skill).strip()
            ]
        
        if isinstance(value.get("technical_skills"), str):
            value["technical_skills"] = [
                x.strip()
                for x in value["technical_skills"].split(",")
                if x.strip()
            ]

        if isinstance(value.get("soft_skills"), str):
            value["soft_skills"] = [
                x.strip()
                for x in value["soft_skills"].split(",")
                if x.strip()
            ]
            
        return value


      

    full_name: Optional[str] = None
    contact_details: ContactDetails = Field(default_factory=ContactDetails)
    professional_summary: Optional[str] = None

    skills: List[str] = Field(default_factory=list)
    technical_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    work_experience: List[WorkExperience] = Field(default_factory=list)
    internships: List[Internship] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    publications: List[Publication] = Field(default_factory=list)
    achievements: List[Achievement] = Field(default_factory=list)
    languages: List[LanguageProficiency] = Field(default_factory=list)

    total_experience_years: Optional[float] = None
    current_job_title: Optional[str] = None
    additional_information: Optional[str] = Field(
    default=None,
    description="Any other relevant information as plain text. Do not return an object or dictionary."
    )


class ParsedResumeData(BaseModel):
    """
    Final structured resume object returned to the API caller.
    Built by merging RegexExtraction (source of truth for contact fields)
    with LLMExtraction (source of truth for everything contextual).
    """

    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio_website: Optional[str] = None

    professional_summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    work_experience: List[WorkExperience] = Field(default_factory=list)
    internships: List[Internship] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    publications: List[Publication] = Field(default_factory=list)
    achievements: List[Achievement] = Field(default_factory=list)
    languages: List[LanguageProficiency] = Field(default_factory=list)
    total_experience_years: Optional[float] = None
    current_job_title: Optional[str] = None
    additional_information: Optional[str] = None


class ParseResumeResponse(BaseModel):
    success: bool = True
    resume_id: uuid.UUID
    filename: str
    message: str = "Resume parsed successfully"
    data: ParsedResumeData


# --------------------------------------------------------------------------- #
# 3. Internship matching (Milestone 2 - RAG pipeline)
#
# Ported from the Milestone 2 prototype's app/schemas.py. Kept as a
# self-contained section so it's obvious this was added on top of the
# Assignment 1 schemas above without touching them.
# --------------------------------------------------------------------------- #


class InternshipPosting(BaseModel):
    """One synthetic internship posting, as stored in app/data/internships.json
    and indexed in FAISS (see app/services/internship_index.py)."""

    id: str
    company: str
    role_title: str
    domain: str
    location: str
    mode: str
    duration_weeks: int
    stipend_inr_per_month: int
    min_education: str
    required_skills: List[str]
    preferred_skills: List[str]
    description: str
    apply_url: Optional[str] = None


class InternshipMatch(InternshipPosting):
    """A posting returned by the matching endpoint, with the weighted
    composite match score and a breakdown of what it's made of (see
    app/services/internship_matcher.py) plus the skill-gap detail."""

    match_score: float  # composite, 0-1 -> 0.5*skill + 0.2*semantic + 0.15*education + 0.15*location
    match_percentage: float  # match_score * 100, for display
    match_label: str  # "Perfect Match" / "Strong Match" / "Partial Match" / "Weak Match"
    semantic_score: float
    skill_score: float
    education_score: float
    location_score: float
    matched_skills: List[str]
    missing_skills: List[str]


class InternshipMatchResponse(BaseModel):
    """Response of GET /internships/match/{resume_id}."""

    resume_id: uuid.UUID
    query_skills: Optional[str] = None
    query_profile: dict = Field(default_factory=dict)
    results: List[InternshipMatch]
    summary: Optional[str] = None


# --------------------------------------------------------------------------- #
# 4. Career profile / cover letters
# --------------------------------------------------------------------------- #

class CustomProfileSection(BaseModel):
    """A user-defined, freeform Career Profile section (name + content),
    added via the "+ Add section" button when the built-in sections
    (education, skills, projects, achievements, experience) aren't enough."""

    id: str
    title: str
    content: str = ""


class CareerProfileUpdate(BaseModel):
    personal_details: dict = Field(default_factory=dict)
    education: list[dict] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    achievements: list[dict] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    custom_sections: list[CustomProfileSection] = Field(default_factory=list)


class CareerProfileResponse(BaseModel):
    personal_details: dict = Field(default_factory=dict)
    education: list[dict] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    achievements: list[dict] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    custom_sections: list[CustomProfileSection] = Field(default_factory=list)
    resume: Optional[dict] = None
    photo_url: Optional[str] = None


class CoverLetterRequest(BaseModel):
    resume_id: uuid.UUID
    internship_id: str


class CoverLetterResponse(BaseModel):
    id: uuid.UUID
    internship_id: str
    internship_role: str
    company: str
    content: str
    created_at: datetime
    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# 5. Parsed Resumes (list/history view - reuses the existing Resume /
#    ParsedResume tables, no new resume storage)
# --------------------------------------------------------------------------- #

class ParsedResumeSummary(BaseModel):
    resume_id: uuid.UUID
    filename: str
    file_type: str
    uploaded_at: datetime
    is_parsed: bool
    is_latest: bool = False


# --------------------------------------------------------------------------- #
# 6. Applied Internships (in-app apply, no external redirect)
# --------------------------------------------------------------------------- #

class AppliedInternshipCreate(BaseModel):
    internship_id: str


class AppliedInternshipResponse(BaseModel):
    id: uuid.UUID
    internship_id: str
    role_title: str
    company: str
    status: str
    applied_at: datetime
    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# 7. AI Assistant / Product Chatbot (RAG + conversation memory)
# --------------------------------------------------------------------------- #

class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ChatSessionCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    message: str
    sources: Optional[list[str]] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ChatSendResponse(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


# --------------------------------------------------------------------------- #
# 8. AI Interview Preparation Agent
#
# Fully separate contract from the AI Assistant / Product Chatbot above
# (section 7). This agent uses the candidate's existing extracted resume
# data (ParsedResume.parsed_json) plus an optionally-uploaded PDF/DOCX
# document as context, and is never mixed with product-knowledge answers.
# --------------------------------------------------------------------------- #


class InterviewPrepContextResponse(BaseModel):
    """Powers the 'Resume context loaded' indicator on the Interview
    Preparation page."""

    resume_loaded: bool
    resume_id: Optional[uuid.UUID] = None
    filename: Optional[str] = None
    name: Optional[str] = None
    current_job_title: Optional[str] = None
    top_skills: List[str] = Field(default_factory=list)
    education_count: int = 0
    experience_count: int = 0
    project_count: int = 0


class InterviewPrepSessionCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    resume_id: Optional[uuid.UUID] = None


class InterviewPrepSessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    resume_id: Optional[uuid.UUID] = None
    document_filename: Optional[str] = None
    has_document: bool = False
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class InterviewPrepMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class InterviewPrepMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    message: str
    created_at: datetime
    model_config = {"from_attributes": True}


class InterviewPrepSendResponse(BaseModel):
    user_message: InterviewPrepMessageResponse
    assistant_message: InterviewPrepMessageResponse


class InterviewPrepDocumentUploadResponse(BaseModel):
    session_id: uuid.UUID
    filename: str
    characters_extracted: int
    message: str = "Document uploaded and ready for Q&A."
