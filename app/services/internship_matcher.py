# ---------------------------------------------------------------------------
# RESUME -> INTERNSHIP MATCHING = the "agent" that ties resume parsing
# (Assignment 1's hybrid Regex+LLM pipeline, via app/services/resume_profile.py)
# together with the internship vector index (app/services/internship_index.py).
#
# Ported from the Milestone 2 prototype (app/services/internship_matcher.py).
# The only structural change from the original: it now takes a
# ResumeMatchProfile (see app/services/resume_profile.py) instead of an ORM
# Resume row with flat skills/education/location columns, since Assignment 1
# stores that data as a nested JSON blob (ParsedResume.parsed_json) instead.
# All scoring/ranking logic is unchanged.
# ---------------------------------------------------------------------------
# Given a resume's match profile, this:
#   1. Builds a query text out of whatever the resume actually has (skills +
#      education + summary + projects/experience, falling back to raw
#      extracted text if those are empty - same "never block, degrade
#      gracefully" approach as the resume parser itself).
#   2. Pulls a WIDER candidate pool from FAISS (not just the final top-k) -
#      semantic similarity alone is a weak final ranking signal, so more
#      candidates are pulled and then re-ranked on the factors that
#      actually matter for "is this internship right for this student":
#        - skill_score:     matched / required skills ratio
#        - semantic_score:  the FAISS similarity (still useful - captures
#                            fit the other 3 scores can't, e.g. domain)
#        - education_score: does the resume's degree level match what the
#                            posting asks for
#        - location_score:  does the resume's location match the posting's
#                            (remote postings always match)
#   3. Combines those into one composite score (skills weighted highest,
#      since that's the primary signal), re-sorts by it, and returns the
#      top-k with the full breakdown so a caller can see *why* something
#      is/isn't a good match, not just a bare number.
#   4. Optionally asks Groq for one short natural-language summary of the
#      whole result set. Best-effort: returns None on any failure, exactly
#      like the resume parser's LLM step - a summary is a nice-to-have, not
#      something a match request should ever fail over.
# ---------------------------------------------------------------------------
from __future__ import annotations

import re

from app.config import get_settings
from app.services.internship_index import list_all_postings, search_similar_internships
from app.services.resume_profile import ResumeMatchProfile

MAX_EXTRACTED_TEXT_CHARS_FOR_QUERY = 2000  # fallback only; skills/education are preferred

CANDIDATE_POOL_MULTIPLIER = 4  # pull ~4x k from FAISS before re-ranking
MIN_CANDIDATE_POOL = 20

WEIGHT_SKILL = 0.50
WEIGHT_SEMANTIC = 0.20
WEIGHT_EDUCATION = 0.15
WEIGHT_LOCATION = 0.15

BACHELORS_RE = re.compile(r"\b(b\.?\s?tech|b\.?\s?e\.?|b\.?\s?sc|bca|bba|bachelor'?s?)\b", re.IGNORECASE)
MASTERS_RE = re.compile(r"\b(m\.?\s?tech|m\.?\s?e\.?|m\.?\s?sc|mca|mba|master'?s?)\b", re.IGNORECASE)
PHD_RE = re.compile(r"ph\.?d", re.IGNORECASE)
DIPLOMA_RE = re.compile(r"diploma", re.IGNORECASE)


def _split_skills(skills: str | None) -> set[str]:
    if not skills:
        return set()
    return {s.strip().lower() for s in skills.split(",") if s.strip()}


def build_query_text(profile: ResumeMatchProfile) -> str:
    """Builds the text to embed and search with. Prefers the structured
    parsed fields (skills, education, summary, projects/experience) since
    they're clean signal; only falls back to raw extracted text if parsing
    came up completely empty."""
    parts = []
    if profile.skills:
        parts.append(f"Skills: {profile.skills}")
    if profile.education:
        parts.append(f"Education: {profile.education}")
    if profile.professional_summary:
        parts.append(f"Summary: {profile.professional_summary}")
    if profile.supporting_text:
        parts.append(f"Projects & Experience: {profile.supporting_text}")

    if parts:
        return "\n".join(parts)

    if profile.extracted_text:
        return profile.extracted_text[:MAX_EXTRACTED_TEXT_CHARS_FOR_QUERY]

    return ""


def _skill_gap(resume_skills: set[str], posting_required: list[str]) -> tuple[list[str], list[str]]:
    matched = [s for s in posting_required if s.lower() in resume_skills]
    missing = [s for s in posting_required if s.lower() not in resume_skills]
    return matched, missing


def _degree_level(text: str) -> str | None:
    """Coarse degree-level classification shared by resumes and postings,
    so "B.Tech" on a resume can be compared against "Pursuing B.Tech/B.E."
    on a posting without needing an exact string match."""
    if MASTERS_RE.search(text):
        return "masters"
    if BACHELORS_RE.search(text):
        return "bachelors"
    if PHD_RE.search(text):
        return "phd"
    if DIPLOMA_RE.search(text):
        return "diploma"
    return None


def _education_score(resume_education: str | None, posting_min_education: str) -> float:
    if not resume_education:
        return 0.5  # unknown - don't penalize
    if "any bachelor" in posting_min_education.lower():
        return 1.0  # posting explicitly accepts any bachelor's-level candidate
    resume_level = _degree_level(resume_education)
    posting_level = _degree_level(posting_min_education)
    if resume_level is None or posting_level is None:
        return 0.5
    return 1.0 if resume_level == posting_level else 0.3


def _city(location: str) -> str:
    return location.split(",")[0].strip().lower()


def _location_score(resume_location: str | None, posting: dict) -> float:
    if posting.get("mode") == "Remote" or _city(posting.get("location", "")) == "remote":
        return 1.0  # location-agnostic postings always match
    if not resume_location:
        return 0.5  # unknown - don't penalize
    resume_city = _city(resume_location)
    posting_city = _city(posting.get("location", ""))
    if not resume_city or not posting_city:
        return 0.5
    return 1.0 if resume_city == posting_city else 0.0


def _match_label(composite: float) -> str:
    if composite >= 0.85:
        return "Perfect Match"
    if composite >= 0.65:
        return "Strong Match"
    if composite >= 0.40:
        return "Partial Match"
    return "Weak Match"


def _summarize_matches(resume_skills_text: str, matches: list[dict]) -> str | None:
    """Best-effort Groq call for a short natural-language summary of the
    result set. Returns None (never raises) if no API key is configured or
    the call fails for any reason."""
    settings = get_settings()
    if not settings.groq_api_key or not matches:
        return None

    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)
        listing = "\n".join(
            f"- {m['role_title']} at {m['company']} ({m['domain']}, {m['match_percentage']}% match): "
            f"requires {', '.join(m['required_skills'])}"
            for m in matches[:5]
        )
        prompt = (
            "A student has these skills: "
            f"{resume_skills_text}\n\n"
            "These internships were found as the closest matches:\n"
            f"{listing}\n\n"
            "In 2-3 sentences, summarize how well the student's skills fit "
            "these internships overall, and suggest 1-2 skills worth "
            "learning to open up more/better matches. Be specific and "
            "concise, no preamble."
        )
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return None


def match_resume_to_internships(profile: ResumeMatchProfile, k: int = 5) -> dict:
    """Returns {query_skills, results, summary}. `results` is always a list
    (possibly empty if the resume has no usable text at all - the caller
    decides whether that's a 400)."""
    query_text = build_query_text(profile)
    if not query_text:
        return {"query_skills": None, "results": [], "summary": None}

    resume_skills = _split_skills(profile.skills)

    catalog_size = len(list_all_postings())
    pool_size = min(catalog_size, max(k * CANDIDATE_POOL_MULTIPLIER, MIN_CANDIDATE_POOL))
    candidates = search_similar_internships(query_text, k=pool_size)

    scored = []
    for posting in candidates:
        matched, missing = _skill_gap(resume_skills, posting["required_skills"])
        skill_score = len(matched) / len(posting["required_skills"]) if posting["required_skills"] else 0.5
        semantic_score = posting["match_score"]  # FAISS-derived, already ~0-1
        education_score = _education_score(profile.education, posting["min_education"])
        location_score = _location_score(profile.location, posting)

        composite = (
            WEIGHT_SKILL * skill_score
            + WEIGHT_SEMANTIC * semantic_score
            + WEIGHT_EDUCATION * education_score
            + WEIGHT_LOCATION * location_score
        )

        scored.append(
            {
                **posting,
                "match_score": round(composite, 4),
                "match_percentage": round(composite * 100, 1),
                "match_label": _match_label(composite),
                "semantic_score": round(semantic_score, 4),
                "skill_score": round(skill_score, 4),
                "education_score": round(education_score, 4),
                "location_score": round(location_score, 4),
                "matched_skills": matched,
                "missing_skills": missing,
            }
        )

    scored.sort(key=lambda m: m["match_score"], reverse=True)
    results = scored[:k]

    summary = _summarize_matches(profile.skills or query_text, results)

    return {"query_skills": profile.skills, "results": results, "summary": summary}
