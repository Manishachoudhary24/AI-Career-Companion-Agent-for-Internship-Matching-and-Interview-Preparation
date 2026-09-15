"""
Resume -> matching-profile adapter.

Why this file exists
---------------------
Assignment 1 (this project) stores parsed resume data as a single JSON blob:
    ParsedResume.parsed_json  (== ParsedResumeData, see app/models/schemas.py)
        skills: List[str], technical_skills: List[str], education: List[Education], ...

The Milestone 2 RAG matcher (ported into app/services/internship_matcher.py)
was originally written against a *different* schema, where a resume had
flat, already-stringified columns directly on the Resume row:
    resume.skills            -> "Python, SQL, React"
    resume.education         -> "B.Tech Computer Science, XYZ University"
    resume.professional_summary
    resume.location
    resume.extracted_text

Rather than changing Assignment 1's Resume table (which would touch the
resume-upload pipeline, migrations, and everything downstream of it), this
module builds a small in-memory "profile" object with that exact flat shape
from the existing ParsedResume.parsed_json + Resume.raw_text. The matcher
then works against this object unmodified, so Assignment 1's storage model
is left completely alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResumeMatchProfile:
    """Flat, matcher-friendly view of a resume. Duck-types the subset of
    fields app/services/internship_matcher.py reads off a "resume" object."""

    skills: str | None = None
    education: str | None = None
    professional_summary: str | None = None
    location: str | None = None
    extracted_text: str | None = None
    # Extra context (projects/experience) folded into the embedding query
    # for richer semantic matching than skills/education alone would give -
    # useful for the assignment's "project-based matching" test cases.
    supporting_text: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "skills": self.skills,
            "education": self.education,
            "professional_summary": self.professional_summary,
            "location": self.location,
        }


def _dedup_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if item.strip() and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def _format_education(education_entries: list[dict]) -> str | None:
    """Flattens the structured `education` list from ParsedResumeData into
    one comparable string, e.g. "B.Tech in Computer Science, XYZ University".
    Mirrors the level of detail the regex used in internship_matcher's
    degree-level classifier (_degree_level) expects to find."""
    parts = []
    for entry in education_entries or []:
        degree = entry.get("degree")
        field_of_study = entry.get("field_of_study")
        institution = entry.get("institution")
        if not any([degree, field_of_study, institution]):
            continue
        piece = degree or ""
        if field_of_study:
            piece = f"{piece} in {field_of_study}".strip()
        if institution:
            piece = f"{piece}, {institution}".strip(", ")
        if piece:
            parts.append(piece)
    return "; ".join(parts) if parts else None


def _format_projects(projects: list[dict], limit: int = 5) -> str:
    lines = []
    for p in (projects or [])[:limit]:
        name = p.get("name") or ""
        desc = p.get("description") or ""
        tech = ", ".join(p.get("technologies_used") or [])
        line = " - ".join(x for x in [name, desc, tech] if x)
        if line:
            lines.append(line)
    return "\n".join(lines)


def _format_experience(work_experience: list[dict], internships: list[dict], limit: int = 5) -> str:
    lines = []
    for entry in (work_experience or [])[:limit]:
        title = entry.get("job_title") or ""
        company = entry.get("company") or ""
        techs = ", ".join(entry.get("technologies_used") or [])
        line = " at ".join(x for x in [title, company] if x)
        if techs:
            line = f"{line} ({techs})" if line else techs
        if line:
            lines.append(line)
    for entry in (internships or [])[:limit]:
        role = entry.get("role") or ""
        org = entry.get("organization") or ""
        desc = entry.get("description") or ""
        line = " - ".join(x for x in [f"{role} at {org}".strip(" at "), desc] if x)
        if line:
            lines.append(line)
    return "\n".join(lines)


def build_resume_match_profile(resume) -> ResumeMatchProfile:
    """Builds a ResumeMatchProfile from a Resume ORM row (with its
    `parsed_resume` relationship loaded). Degrades gracefully: a resume
    that hasn't been parsed yet (or parsed with mostly-empty fields) still
    produces a profile - callers fall back to extracted_text, same as the
    ported matcher's original design."""
    parsed = getattr(resume, "parsed_resume", None)
    data: dict[str, Any] = (parsed.parsed_json or {}) if parsed else {}

    all_skills = _dedup_preserve_order(
        [*(data.get("skills") or []), *(data.get("technical_skills") or [])]
    )
    skills_str = ", ".join(all_skills) if all_skills else None

    education_str = _format_education(data.get("education") or [])

    professional_summary = data.get("professional_summary")
    location = data.get("address")

    supporting_text = "\n".join(
        filter(
            None,
            [
                _format_projects(data.get("projects") or []),
                _format_experience(data.get("work_experience") or [], data.get("internships") or []),
            ],
        )
    )

    return ResumeMatchProfile(
        skills=skills_str,
        education=education_str,
        professional_summary=professional_summary,
        location=location,
        extracted_text=getattr(resume, "raw_text", None),
        supporting_text=supporting_text,
    )
