"""
Contextual / semantic resume field extraction using Groq via LangChain.

Pipeline:

    Resume text
        ↓
    Groq LLM (normal chat - NO tool/function calling)
        ↓
    JSON text
        ↓
    JSON extraction
        ↓
    Normalization
        ↓
    Existing LLMExtraction Pydantic schema

IMPORTANT:
- Does NOT use with_structured_output()
- Does NOT use function calling
- Does NOT use Groq tool calling
- Keeps the existing Pydantic schema
- Keeps all existing resume fields
- Normalizes common LLM variations
- Uses retries for transient failures
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.models.schemas import LLMExtraction


logger = logging.getLogger(__name__)


# ============================================================
# ERROR
# ============================================================

class LLMExtractionError(Exception):
    """Raised when Groq resume extraction fails."""
    pass


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an expert resume/CV information extraction system.

Your job is to read the COMPLETE resume text and extract EVERY piece of
useful information into the JSON structure requested below.

CRITICAL RULES:

1. Extract information ONLY from the supplied resume.
2. NEVER invent information.
3. NEVER omit information that is clearly present.
4. Preserve the candidate's actual wording where practical.
5. Do not summarize away important details.
6. If a section exists in the resume, extract it.
7. If a section does not exist, return an empty array or null.
8. Return ONLY one valid JSON object.
9. Do NOT return Markdown.
10. Do NOT return ```json.
11. Do NOT return explanations before or after the JSON.
12. Do NOT use comments inside JSON.

============================================================
FIELD RULES
============================================================

full_name:
Extract the candidate's complete name.

contact_details:
Extract:
- email
- phone
- address
- city
- state
- country
- linkedin
- github
- portfolio_website

professional_summary:
Use the career objective/profile/summary from the resume.
If no summary exists, create a short summary ONLY from information
actually present in the resume.

============================================================
SKILLS
============================================================

This is extremely important.

Read the ENTIRE resume for skills.

Extract skills from:
- SKILLS section
- internships
- projects
- work experience
- certifications
- technical descriptions

technical_skills MUST contain:
- programming languages
- frameworks
- libraries
- databases
- tools
- platforms
- APIs
- authentication technologies
- cloud technologies
- AI/ML technologies
- web technologies
- development technologies

Examples:
Java
C
Python
HTML
CSS
JavaScript
MySQL
Spring Boot
Node.js
Express.js
WebRTC
WebSocket
JWT
REST APIs
OpenCV
DeepFace
Git

soft_skills MUST contain:
- communication
- teamwork
- leadership
- adaptability
- time management
- problem solving
- creativity
- etc.

skills MUST be a FLAT ARRAY containing the union of:
technical_skills + soft_skills.

DO NOT make skills an object.

Programming languages belong in technical_skills,
NOT languages.

============================================================
EDUCATION
============================================================

Extract EVERY education entry.

For every entry extract:
- institution
- degree
- details
- start_date
- end_date

Preserve:
- CGPA
- percentage
- board/university
- academic details

============================================================
WORK EXPERIENCE
============================================================

Extract professional employment that is NOT an internship.

For every entry extract:
- company
- title
- start_date
- end_date
- description

Description MUST be a single string.

============================================================
INTERNSHIPS
============================================================

Extract EVERY internship.

For every internship extract:
- company
- title
- start_date
- end_date
- description

If the resume contains multiple bullet points, combine them into
ONE readable string.

Do NOT discard technologies mentioned in internship descriptions.

============================================================
PROJECTS
============================================================

Extract EVERY project.

Include:
- academic projects
- mini projects
- personal projects
- major projects
- freelance projects

For every project extract:
- title
- description
- technologies

Description MUST be a single string.

Technologies MUST contain all technologies explicitly mentioned
for that project.

============================================================
CERTIFICATIONS
============================================================

Extract EVERY certification.

For every certification extract:
- name
- issuing_organization
- issue_date
- expiry_date
- credential_id

If only the certification name is available, still create the entry.

============================================================
PUBLICATIONS
============================================================

Extract every publication if present.

============================================================
ACHIEVEMENTS
============================================================

Extract EVERY:
- achievement
- award
- hackathon
- coding event
- competition
- recognition
- workshop if relevant

Do NOT silently discard achievements.

============================================================
LANGUAGES
============================================================

languages contains ONLY human/spoken languages.

Examples:
English
Kannada
Hindi

Do NOT put:
Java
Python
C
JavaScript

inside languages.

If proficiency is mentioned, preserve it.

============================================================
EXPERIENCE
============================================================

total_experience_years:
Calculate only when reasonably possible from the dates.

Otherwise return null.

current_job_title:
Use the current role if clearly stated.

============================================================
ADDITIONAL INFORMATION
============================================================

Put information that does not fit another field here.

Examples:
- interests
- hobbies
- volunteering
- availability
- other noteworthy information

Return this as ONE plain string or null.

============================================================
VERY IMPORTANT OUTPUT REQUIREMENT
============================================================

Return exactly ONE JSON object with these top-level fields:

{
  "full_name": null,
  "contact_details": {
    "email": null,
    "phone": null,
    "address": null,
    "city": null,
    "state": null,
    "country": null,
    "linkedin": null,
    "github": null,
    "portfolio_website": null
  },
  "professional_summary": null,

  "skills": [],

  "technical_skills": [],
  "soft_skills": [],

  "education": [],
  "work_experience": [],
  "internships": [],
  "projects": [],
  "certifications": [],
  "publications": [],
  "achievements": [],
  "languages": [],

  "total_experience_years": null,
  "current_job_title": null,
  "additional_information": null
}

IMPORTANT:

"skills" = array of strings.

"technical_skills" = array of strings.

"soft_skills" = array of strings.

"languages" = array of objects:
{
    "name": "English",
    "proficiency": null
}

"certifications" = array of objects.

"internships" = array of objects.

"projects" = array of objects.

"education" = array of objects.

Descriptions must be strings, never arrays.

Return the actual information found in the resume.
"""


# ============================================================
# USER PROMPT
# ============================================================

USER_PROMPT = """
Read the following COMPLETE resume text carefully.

Extract ALL available information.

Do not skip sections.

Do not invent anything.

--- BEGIN RESUME ---

{resume_text}

--- END RESUME ---

Return ONLY the JSON object.
"""


# ============================================================
# BUILD GROQ LLM
# ============================================================

def _build_llm() -> ChatGroq:
    settings = get_settings()

    if not settings.groq_api_key:
        raise LLMExtractionError(
            "GROQ_API_KEY is not configured. "
            "Set it in the .env file."
        )

    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
         temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        model_kwargs={
            "response_format": {"type": "json_object"}
        },
    )


# ============================================================
# JSON EXTRACTION
# ============================================================

def _extract_json(text: str) -> dict[str, Any]:
    """
    Extract a JSON object from Groq's normal text response.

    Handles:
    - pure JSON
    - ```json ... ```
    - surrounding text
    - JSON surrounded by explanations
    """

    if not text:
        raise LLMExtractionError(
            "Groq returned an empty response."
        )

    text = text.strip()

    # Remove markdown fences.
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = text.strip()

    # --------------------------------------------------------
    # Direct JSON
    # --------------------------------------------------------

    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Find JSON object inside response
    # --------------------------------------------------------

    start = text.find("{")

    if start == -1:
        raise LLMExtractionError(
            "Groq response did not contain a JSON object."
        )

    # Use JSONDecoder instead of simply using rfind("}")
    # because nested objects are present.
    decoder = json.JSONDecoder()

    try:
        parsed, _ = decoder.raw_decode(text[start:])

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError as exc:

        # Last attempt: find outermost JSON object.
        end = text.rfind("}")

        if end > start:

            candidate = text[start:end + 1]

            try:
                parsed = json.loads(candidate)

                if isinstance(parsed, dict):
                    return parsed

            except json.JSONDecodeError:
                pass

        raise LLMExtractionError(
            f"Groq returned invalid JSON: {exc}"
        ) from exc

    raise LLMExtractionError(
        "Groq response did not contain a valid JSON object."
    )


# ============================================================
# STRING NORMALIZATION
# ============================================================

def _to_string(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        return " ".join(
            str(item).strip()
            for item in value
            if str(item).strip()
        )

    if isinstance(value, dict):
        return "; ".join(
            f"{key}: {val}"
            for key, val in value.items()
        )

    return str(value).strip()


def _to_string_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        # Support comma-separated strings.
        return [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

    if isinstance(value, list):
        result = []

        for item in value:

            if isinstance(item, str):
                item = item.strip()

                if item:
                    result.append(item)

            elif isinstance(item, dict):

                # Try common skill formats.
                for key in (
                    "name",
                    "skill",
                    "title",
                    "technology",
                ):
                    if item.get(key):
                        result.append(
                            str(item[key]).strip()
                        )
                        break

        return result

    return [str(value).strip()]


def _unique_strings(values: list[str]) -> list[str]:
    result = []
    seen = set()

    for value in values:

        value = str(value).strip()

        if not value:
            continue

        key = value.lower()

        if key not in seen:
            seen.add(key)
            result.append(value)

    return result


# ============================================================
# NORMALIZE CONTACT DETAILS
# ============================================================

def _normalize_contact_details(data: dict[str, Any]) -> None:

    contact = data.get("contact_details")

    if not isinstance(contact, dict):
        contact = {}

    # Some LLM responses may put contact fields at root level.
    mappings = {
        "email": "email",
        "phone": "phone",
        "address": "address",
        "city": "city",
        "state": "state",
        "country": "country",
        "linkedin": "linkedin",
        "github": "github",
        "portfolio": "portfolio_website",
        "portfolio_website": "portfolio_website",
    }

    for source_key, target_key in mappings.items():

        if not contact.get(target_key):

            value = data.get(source_key)

            if value:
                contact[target_key] = value

    data["contact_details"] = contact


# ============================================================
# NORMALIZE SKILLS
# ============================================================

def _normalize_skills(data: dict[str, Any]) -> None:

    technical = _to_string_list(
        data.get("technical_skills")
    )

    soft = _to_string_list(
        data.get("soft_skills")
    )

    skills = data.get("skills")

    # Handle:
    #
    # "skills": {
    #   "technical_skills": [...],
    #   "soft_skills": [...]
    # }
    #
    if isinstance(skills, dict):

        technical.extend(
            _to_string_list(
                skills.get("technical_skills")
            )
        )

        soft.extend(
            _to_string_list(
                skills.get("soft_skills")
            )
        )

        skills = []

    else:
        skills = _to_string_list(skills)

    technical = _unique_strings(technical)
    soft = _unique_strings(soft)
    skills = _unique_strings(
        skills + technical + soft
    )

    data["skills"] = skills
    data["technical_skills"] = technical
    data["soft_skills"] = soft


# ============================================================
# NORMALIZE DESCRIPTIONS
# ============================================================

def _normalize_description_items(
    items: Any,
) -> list[dict[str, Any]]:

    if not isinstance(items, list):
        return []

    normalized = []

    for item in items:

        if isinstance(item, str):
            normalized.append(
                {
                    "description": item.strip()
                }
            )
            continue

        if not isinstance(item, dict):
            continue

        item = dict(item)

        if "description" in item:
            item["description"] = _to_string(
                item.get("description")
            )

        normalized.append(item)

    return normalized


# ============================================================
# NORMALIZE EDUCATION
# ============================================================

def _normalize_education(data: dict[str, Any]) -> None:

    education = data.get("education", [])

    if not isinstance(education, list):
        data["education"] = []
        return

    normalized = []

    for item in education:

        if isinstance(item, str):

            normalized.append(
                {
                    "institution": item,
                    "degree": None,
                    "details": None,
                    "start_date": None,
                    "end_date": None,
                }
            )

            continue

        if not isinstance(item, dict):
            continue

        item = dict(item)

        # Common alternative field names.
        if not item.get("institution"):
            item["institution"] = (
                item.get("school")
                or item.get("college")
                or item.get("university")
            )

        if not item.get("degree"):
            item["degree"] = (
                item.get("qualification")
                or item.get("program")
            )

        if not item.get("details"):
            details = []

            for key in (
                "cgpa",
                "gpa",
                "percentage",
                "grade",
                "board",
            ):

                if item.get(key) is not None:
                    details.append(
                        f"{key}: {item[key]}"
                    )

            if details:
                item["details"] = " | ".join(
                    details
                )

        normalized.append(item)

    data["education"] = normalized


# ============================================================
# NORMALIZE INTERNSHIPS / WORK / PROJECTS
# ============================================================

def _normalize_experience(data: dict[str, Any]) -> None:

    for field in (
        "internships",
        "work_experience",
        "projects",
    ):

        items = data.get(field, [])

        if not isinstance(items, list):
            data[field] = []
            continue

        normalized = []

        for item in items:

            if not isinstance(item, dict):
                continue

            item = dict(item)

            if "description" in item:
                item["description"] = _to_string(
                    item.get("description")
                )

            # Technologies may arrive as a string.
            if field == "projects":

                item["technologies"] = _to_string_list(
                    item.get("technologies", [])
                )

            normalized.append(item)

        data[field] = normalized


# ============================================================
# NORMALIZE CERTIFICATIONS
# ============================================================

def _normalize_certifications(
    data: dict[str, Any]
) -> None:

    certifications = data.get(
        "certifications",
        [],
    )

    if not isinstance(certifications, list):
        data["certifications"] = []
        return

    normalized = []

    for item in certifications:

        if isinstance(item, str):

            value = item.strip()

            if not value:
                continue

            name = value
            organization = None
            issue_date = None

            # Example:
            # Machine Learning Foundations,
            # AWS Academy, 2026
            parts = [
                p.strip()
                for p in value.split(",")
                if p.strip()
            ]

            if len(parts) >= 2:
                name = parts[0]
                organization = parts[1]

            if len(parts) >= 3:
                issue_date = parts[2]

            # Example:
            # Introduction to C-programming - Solo Learn
            if " - " in value:

                name, organization = value.split(
                    " - ",
                    1,
                )

                name = name.strip()
                organization = organization.strip()

            normalized.append(
                {
                    "name": name,
                    "issuing_organization": organization,
                    "issue_date": issue_date,
                    "expiry_date": None,
                    "credential_id": None,
                }
            )

        elif isinstance(item, dict):

            normalized.append(dict(item))

    data["certifications"] = normalized


# ============================================================
# NORMALIZE LANGUAGES
# ============================================================

def _normalize_languages(
    data: dict[str, Any]
) -> None:

    languages = data.get(
        "languages",
        [],
    )

    if not isinstance(languages, list):
        data["languages"] = []
        return

    normalized = []

    for item in languages:

        if isinstance(item, str):

            value = item.strip()

            if not value:
                continue

            proficiency = None

            # English (Fluent)
            if "(" in value and value.endswith(")"):

                name, prof = value.rsplit(
                    "(",
                    1,
                )

                value = name.strip()
                proficiency = prof[:-1].strip()

            normalized.append(
                {
                    "name": value,
                    "proficiency": proficiency,
                }
            )

        elif isinstance(item, dict):

            item = dict(item)

            if (
                "language" in item
                and "name" not in item
            ):
                item["name"] = item.pop(
                    "language"
                )

            normalized.append(item)

    data["languages"] = normalized


# ============================================================
# NORMALIZE ACHIEVEMENTS
# ============================================================

def _normalize_achievements(
    data: dict[str, Any]
) -> None:

    achievements = data.get(
        "achievements",
        [],
    )

    if not isinstance(achievements, list):
        data["achievements"] = []
        return

    normalized = []

    for item in achievements:

        if isinstance(item, str):

            normalized.append(
                {
                    "name": item.strip(),
                    "description": None,
                    "date": None,
                }
            )

        elif isinstance(item, dict):

            item = dict(item)

            # Support title -> name.
            if (
                not item.get("name")
                and item.get("title")
            ):
                item["name"] = item.pop(
                    "title"
                )

            if "description" in item:
                item["description"] = _to_string(
                    item.get("description")
                )

            normalized.append(item)

    data["achievements"] = normalized


# ============================================================
# NORMALIZE PUBLICATIONS
# ============================================================

def _normalize_publications(
    data: dict[str, Any]
) -> None:

    publications = data.get(
        "publications",
        [],
    )

    if not isinstance(publications, list):
        data["publications"] = []
        return

    normalized = []

    for item in publications:

        if isinstance(item, str):

            normalized.append(
                {
                    "title": item.strip(),
                    "publisher": None,
                    "date": None,
                    "link": None,
                    "description": None,
                }
            )

        elif isinstance(item, dict):

            item = dict(item)

            if "description" in item:
                item["description"] = _to_string(
                    item.get("description")
                )

            normalized.append(item)

    data["publications"] = normalized


# ============================================================
# NORMALIZE COMPLETE LLM OUTPUT
# ============================================================

def _normalize_extraction(
    data: dict[str, Any]
) -> dict[str, Any]:

    data = dict(data)

    # --------------------------------------------------------
    # Root-level aliases
    # --------------------------------------------------------

    if not data.get("full_name"):
        data["full_name"] = (
            data.get("name")
            or data.get("candidate_name")
        )

    _normalize_contact_details(data)

    # --------------------------------------------------------
    # Skills
    # --------------------------------------------------------

    _normalize_skills(data)

    # --------------------------------------------------------
    # Main structured sections
    # --------------------------------------------------------

    _normalize_education(data)

    _normalize_experience(data)

    _normalize_certifications(data)

    _normalize_languages(data)

    _normalize_achievements(data)

    _normalize_publications(data)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    if data.get("professional_summary") is not None:

        data["professional_summary"] = _to_string(
            data["professional_summary"]
        )

    # --------------------------------------------------------
    # Additional information
    # --------------------------------------------------------

    additional = data.get(
        "additional_information"
    )

    if isinstance(additional, dict):

        parts = []

        for key, value in additional.items():

            if isinstance(value, list):
                value = ", ".join(
                    str(x)
                    for x in value
                )

            parts.append(
                f"{key}: {value}"
            )

        data["additional_information"] = (
            "; ".join(parts)
        )

    elif isinstance(additional, list):

        data["additional_information"] = (
            " ".join(
                str(x)
                for x in additional
            )
        )

    elif additional is not None:

        data["additional_information"] = str(
            additional
        )

    # --------------------------------------------------------
    # Ensure all expected top-level fields exist.
    # --------------------------------------------------------

    defaults = {
        "full_name": None,
        "contact_details": {},
        "professional_summary": None,
        "skills": [],
        "technical_skills": [],
        "soft_skills": [],
        "education": [],
        "work_experience": [],
        "internships": [],
        "projects": [],
        "certifications": [],
        "publications": [],
        "achievements": [],
        "languages": [],
        "total_experience_years": None,
        "current_job_title": None,
        "additional_information": None,
    }

    for key, default in defaults.items():

        if key not in data:
            data[key] = default

    return data


# ============================================================
# INVOKE GROQ
# ============================================================

@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(
        multiplier=2,
        min=3,
        max=15,
    ),
    retry=retry_if_exception_type(
        LLMExtractionError
    ),
)
def _invoke_llm(
    llm: ChatGroq,
    resume_text: str,
) -> LLMExtraction:

    messages = [
        SystemMessage(
            content=SYSTEM_PROMPT
        ),
        HumanMessage(
            content=USER_PROMPT.format(
                resume_text=resume_text
            )
        ),
    ]

    logger.info(
        "Sending resume to Groq for semantic extraction"
    )

    response = llm.invoke(messages)

    # --------------------------------------------------------
    # Extract response content
    # --------------------------------------------------------

    content = getattr(
        response,
        "content",
        None,
    )

    if isinstance(content, list):

        parts = []

        for block in content:

            if isinstance(block, str):
                parts.append(block)

            elif isinstance(block, dict):

                if block.get("text"):
                    parts.append(
                        str(block["text"])
                    )

        content = "".join(parts)

    if not isinstance(content, str):
        content = str(content or "")

    logger.info(
        "Groq returned %d characters",
        len(content),
    )

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    parsed = _extract_json(content)

    logger.debug(
        "Raw Groq extraction: %s",
        json.dumps(
            parsed,
            ensure_ascii=False,
            default=str,
        )[:10000],
    )

    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    normalized = _normalize_extraction(
        parsed
    )

    logger.info(
        "Normalized extraction: "
        "technical_skills=%d, soft_skills=%d, "
        "education=%d, internships=%d, "
        "projects=%d, certifications=%d, "
        "achievements=%d, languages=%d",
        len(
            normalized.get(
                "technical_skills",
                []
            )
        ),
        len(
            normalized.get(
                "soft_skills",
                []
            )
        ),
        len(
            normalized.get(
                "education",
                []
            )
        ),
        len(
            normalized.get(
                "internships",
                []
            )
        ),
        len(
            normalized.get(
                "projects",
                []
            )
        ),
        len(
            normalized.get(
                "certifications",
                []
            )
        ),
        len(
            normalized.get(
                "achievements",
                []
            )
        ),
        len(
            normalized.get(
                "languages",
                []
            )
        ),
    )

    # --------------------------------------------------------
    # Pydantic validation
    # --------------------------------------------------------

    try:

        result = LLMExtraction.model_validate(
            normalized
        )

        return result

    except Exception as exc:

        logger.error(
            "LLMExtraction validation failed: %s",
            exc,
        )

        logger.error(
            "Normalized data:\n%s",
            json.dumps(
                normalized,
                indent=2,
                ensure_ascii=False,
                default=str,
            )[:15000],
        )

        raise LLMExtractionError(
            "Groq extraction was received, but "
            "it could not be converted to the "
            "existing LLMExtraction schema: "
            f"{exc}"
        ) from exc


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def extract_llm_fields(
    resume_text: str,
) -> LLMExtraction:
    """
    Extract structured resume information.

    Uses:
        Groq
        LangChain
        JSON parsing
        normalization
        Pydantic validation

    No function/tool calling is used.
    """

    max_chars = 20_000

    if not resume_text or not resume_text.strip():

        raise LLMExtractionError(
            "Resume text is empty. "
            "Unable to perform LLM extraction."
        )

    truncated_text = resume_text[:max_chars]

    try:

        llm = _build_llm()

        return _invoke_llm(
            llm,
            truncated_text,
        )

    except LLMExtractionError:

        logger.exception(
            "LLM extraction failed"
        )

        raise

    except Exception as exc:

        logger.exception(
            "Unexpected LLM extraction error"
        )

        raise LLMExtractionError(
            f"LLM extraction failed: {exc}"
        ) from exc