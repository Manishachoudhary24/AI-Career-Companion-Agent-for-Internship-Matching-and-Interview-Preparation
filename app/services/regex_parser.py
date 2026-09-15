"""
Deterministic field extraction using regular expressions.

Ported from the original hybrid resume-parser project's
`extractors/regex_extractor.py`.

Regex is the source of truth for fields that have a rigid, well-known
pattern: emails, phone numbers, LinkedIn/GitHub/portfolio URLs.
Name extraction is also attempted heuristically (regex + positional
heuristics), but is treated as a *fallback* - the LLM's `full_name`
takes priority when both are present and disagree.
"""
from __future__ import annotations

import re

from app.models.schemas import RegexExtraction

# --------------------------------------------------------------------------- #
# Patterns
# --------------------------------------------------------------------------- #
EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9][a-zA-Z0-9._%+\-]*@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# Matches most international phone formats: +91 98765 43210, (555) 123-4567,
# 555-123-4567, 555.123.4567, 9876543210 etc. Requires 9-15 digits total.
PHONE_PATTERN = re.compile(
    r"(?:(?:\+|00)\d{1,3}[\s.\-]?)?"          # optional country code
    r"(?:\(\d{2,4}\)[\s.\-]?)?"               # optional area code in parens
    r"\d{3,5}[\s.\-]?\d{3,4}[\s.\-]?\d{0,4}"  # main number groups
)

LINKEDIN_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/[A-Za-z0-9\-_%/]+",
    re.IGNORECASE,
)

GITHUB_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9\-_]+",
    re.IGNORECASE,
)

TWITTER_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+",
    re.IGNORECASE,
)

# Generic personal website / portfolio (excludes the platforms handled above).
# Negative lookbehind for '@' prevents matching the domain half of an email
# address. Bare '.com' domains are only matched when explicitly prefixed
# with http(s):// or www. to avoid false positives from company names, etc.
PORTFOLIO_PATTERN = re.compile(
    r"(?<!@)\b(?:(?:https?://)?www\.[A-Za-z0-9\-]+\.com(?:/[A-Za-z0-9\-_/]*)?"
    r"|(?:https?://)?(?:www\.)?[A-Za-z0-9\-]+\.(?:dev|me|io|in|portfolio\.com)"
    r"(?:/[A-Za-z0-9\-_/]*)?)",
    re.IGNORECASE,
)

EXCLUDED_PORTFOLIO_DOMAINS = ("linkedin.com", "github.com", "twitter.com", "x.com")

NAME_LINE_BLOCKLIST = re.compile(
    r"resume|curriculum vitae|\bcv\b|address|phone|email|linkedin|github|"
    r"objective|summary|profile|contact",
    re.IGNORECASE,
)


def _looks_like_phone(candidate: str) -> bool:
    digits = re.sub(r"\D", "", candidate)
    return 9 <= len(digits) <= 15


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower().strip().rstrip("/")
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result


def _guess_name(text: str) -> str | None:
    """
    Heuristic: the candidate's name is almost always on one of the first
    few non-empty lines, is short (2-4 words), title-cased, and doesn't
    contain contact keywords or punctuation typical of headers.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines[:6]:
        if NAME_LINE_BLOCKLIST.search(line):
            continue
        if EMAIL_PATTERN.search(line) or "http" in line.lower():
            continue
        words = line.split()
        if not (2 <= len(words) <= 4):
            continue
        # Reject lines with digits or excessive punctuation (headers/addresses)
        if re.search(r"\d", line):
            continue
        alpha_words = [w for w in words if re.match(r"^[A-Za-z.\-']+$", w)]
        if len(alpha_words) != len(words):
            continue
        # Prefer Title Case or ALL CAPS lines
        if all(w[0].isupper() for w in words if w):
            return " ".join(words)
    return None


def extract_regex_fields(text: str) -> RegexExtraction:
    """Run all deterministic extractors over the raw resume text."""

    emails = _dedupe_preserve_order(EMAIL_PATTERN.findall(text))

    phone_candidates = [
        m.strip() for m in PHONE_PATTERN.findall(text) if _looks_like_phone(m)
    ]
    phone_numbers = _dedupe_preserve_order(phone_candidates)

    linkedin_matches = _dedupe_preserve_order(LINKEDIN_PATTERN.findall(text))
    github_matches = _dedupe_preserve_order(GITHUB_PATTERN.findall(text))
    twitter_matches = _dedupe_preserve_order(TWITTER_PATTERN.findall(text))

    portfolio_matches = []
    for candidate in PORTFOLIO_PATTERN.findall(text):
        low = candidate.lower()
        if any(domain in low for domain in EXCLUDED_PORTFOLIO_DOMAINS):
            continue
        portfolio_matches.append(candidate)
    portfolio_matches = _dedupe_preserve_order(portfolio_matches)

    name = _guess_name(text)

    return RegexExtraction(
        name=name,
        emails=emails,
        phone_numbers=phone_numbers,
        linkedin=linkedin_matches[0] if linkedin_matches else None,
        github=github_matches[0] if github_matches else None,
        portfolio_website=portfolio_matches[0] if portfolio_matches else None,
        twitter=twitter_matches[0] if twitter_matches else None,
    )
