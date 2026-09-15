"""
Orchestrates the hybrid resume-parsing pipeline:

    file bytes -> raw text -> [regex extraction || llm extraction] -> merge

Ported from the original hybrid resume-parser project's
`services/resume_parser_service.py`.

Merge strategy
--------------
- Deterministic contact fields (email, phone, LinkedIn, GitHub, portfolio):
  regex output is authoritative because it is precise and pattern-safe.
  The LLM's version is used only as a fallback when regex found nothing.
- Contextual / semantic fields (summary, skills, education, experience,
  projects, certifications, achievements, languages, etc.): the LLM output
  is authoritative, since these require understanding meaning and cannot
  be reliably captured with patterns.
- `name`: LLM's `full_name` is preferred (it has full document context and
  handles multi-line/creative resume headers better), falling back to the
  regex heuristic guess if the LLM returns nothing.
"""
from __future__ import annotations

import logging

from app.models.schemas import LLMExtraction, ParsedResumeData, RegexExtraction
from app.services.docx_parser import extract_text
from app.services.llm_parser import extract_llm_fields
from app.services.regex_parser import extract_regex_fields

logger = logging.getLogger(__name__)


def _first_or_none(items: list[str]) -> str | None:
    return items[0] if items else None


def merge_extractions(regex_data: RegexExtraction, llm_data: LLMExtraction) -> ParsedResumeData:
    contact = llm_data.contact_details

    name = llm_data.full_name or regex_data.name
    email = _first_or_none(regex_data.emails) or contact.email
    phone = _first_or_none(regex_data.phone_numbers) or contact.phone
    linkedin = regex_data.linkedin or contact.linkedin
    github = regex_data.github or contact.github
    portfolio = regex_data.portfolio_website or contact.portfolio_website

    address_parts = [p for p in (contact.address, contact.city, contact.state, contact.country) if p]
    # Avoid duplicate info if `address` already contains city/state/country
    address = contact.address or (", ".join(dict.fromkeys(address_parts)) if address_parts else None)

    return ParsedResumeData(
        name=name,
        email=email,
        phone_number=phone,
        address=address,
        linkedin=linkedin,
        github=github,
        portfolio_website=portfolio,
        professional_summary=llm_data.professional_summary,
        skills=llm_data.skills,
        technical_skills=llm_data.technical_skills,
        soft_skills=llm_data.soft_skills,
        education=llm_data.education,
        work_experience=llm_data.work_experience,
        internships=llm_data.internships,
        projects=llm_data.projects,
        certifications=llm_data.certifications,
        publications=llm_data.publications,
        achievements=llm_data.achievements,
        languages=llm_data.languages,
        total_experience_years=llm_data.total_experience_years,
        current_job_title=llm_data.current_job_title,
        additional_information=llm_data.additional_information,
    )


def run_hybrid_parser(filename: str, file_bytes: bytes) -> tuple[str, RegexExtraction, LLMExtraction, ParsedResumeData]:
    """
    Full pipeline entry point: takes raw uploaded file bytes and filename,
    returns (raw_text, regex_data, llm_data, merged_parsed_resume).
    """
    logger.info("Extracting text from '%s'", filename)
    raw_text = extract_text(filename, file_bytes)

    logger.info("Running regex extraction")
    regex_data = extract_regex_fields(raw_text)

    logger.info("Running LLM extraction (Groq: %s)", filename)
    llm_data = extract_llm_fields(raw_text)

    logger.info("Merging regex + LLM outputs")
    merged = merge_extractions(regex_data, llm_data)

    return raw_text, regex_data, llm_data, merged
