"""
Extracts raw text from PDF resumes using PyMuPDF.

Ported from the original hybrid resume-parser project's
`extractors/file_parser.py` (PDF half).
"""
from __future__ import annotations

import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class FileParsingError(Exception):
    pass


def _normalize_whitespace(text: str) -> str:
    """Collapse excessive blank lines / trailing spaces while keeping structure."""
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned: list[str] = []
    blank_streak = 0
    for line in lines:
        if line.strip() == "":
            blank_streak += 1
            if blank_streak > 1:
                continue
        else:
            blank_streak = 0
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF using PyMuPDF, preserving reading order per page."""
    try:
        text_chunks: list[str] = []
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                # "text" mode keeps a reasonable reading order for single/multi column resumes
                page_text = page.get_text("text")
                if page_text:
                    text_chunks.append(page_text)
        text = "\n".join(text_chunks)
        if not text.strip():
            raise FileParsingError(
                "No extractable text found in PDF. The file may be a scanned image "
                "without a text layer (OCR is not supported in this version)."
            )
        return _normalize_whitespace(text)
    except FileParsingError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to parse PDF")
        raise FileParsingError(f"Could not parse PDF file: {exc}") from exc
