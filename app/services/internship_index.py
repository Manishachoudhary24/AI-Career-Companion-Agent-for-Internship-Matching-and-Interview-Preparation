# ---------------------------------------------------------------------------
# INTERNSHIP VECTOR INDEX - embed every posting in app/data/internships.json
# and store the vectors in a FAISS index for similarity search.
#
# Ported from the Milestone 2 prototype (app/services/internship_index.py),
# adapted only to use this project's app.config.get_settings() pattern
# instead of a module-level `settings` singleton. Logic is unchanged.
# ---------------------------------------------------------------------------
# Two things live here:
#   1. build_index() - a one-off (re-runnable) step that reads the synthetic
#      postings, embeds each one, and saves a FAISS index to disk. Run it
#      whenever internships.json changes:
#          python -m app.services.internship_index
#      (the app also auto-builds this on startup if it's missing - see
#      app/main.py - so this is only needed for a manual rebuild.)
#   2. search_similar_internships() - what the matching endpoint actually
#      calls at request time. It loads the already-built index (once per
#      process, then cached) and returns the top-k most similar postings to
#      whatever query text it's given (usually a resume's skills/education).
#
# Postings and resumes are embedded into the *same* vector space, so
# "distance between vectors" doubles as "how similar this resume's skills
# are to what this posting is asking for" - that's the whole RAG mechanism.
# ---------------------------------------------------------------------------
from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import get_settings
from app.services.embeddings import get_shared_embeddings

logger = logging.getLogger("ai_career_companion.internship_index")

# Resolves paths relative to the project root regardless of where the
# process is launched from (this file lives at app/services/, so
# parent.parent.parent steps back out to the project root).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Cached at module level so the (relatively slow) embedding model + FAISS
# index are only loaded once per process, not on every request.
_vectorstore: FAISS | None = None
_postings_cache: list[dict] | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    # Delegates to the shared loader (app.services.embeddings) so the same
    # in-memory model instance is reused by the Product Knowledge index too,
    # instead of loading sentence-transformers twice.
    return get_shared_embeddings()


def _posting_to_text(posting: dict) -> str:
    """Turns one posting's fields into a single text blob to embed. Order/
    repetition here matters for retrieval quality: skills are what a
    resume's query text is mostly made of, so they're included plainly
    (not buried in a sentence) to weigh them appropriately."""
    parts = [
        f"{posting['role_title']} at {posting['company']}",
        f"Domain: {posting['domain']}",
        f"Required skills: {', '.join(posting['required_skills'])}",
        f"Preferred skills: {', '.join(posting['preferred_skills'])}",
        f"Minimum education: {posting['min_education']}",
        posting["description"],
    ]
    return "\n".join(parts)


def _load_postings() -> list[dict]:
    settings = get_settings()
    path = PROJECT_ROOT / settings.internship_data_path
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_all_postings() -> list[dict]:
    """All postings from internships.json, cached in memory after the first
    call. Used by GET /internships/ to let the frontend browse the catalog
    without going through the vector index."""
    global _postings_cache
    if _postings_cache is None:
        _postings_cache = _load_postings()
    return _postings_cache


def build_index() -> None:
    """Reads app/data/internships.json, embeds every posting, and saves a
    FAISS index to settings.internship_index_dir. Safe to re-run any time
    the postings dataset changes."""
    settings = get_settings()
    postings = _load_postings()
    documents = [
        Document(page_content=_posting_to_text(p), metadata=p) for p in postings
    ]

    embeddings = _get_embeddings()
    vectorstore = FAISS.from_documents(documents, embeddings)

    index_dir = PROJECT_ROOT / settings.internship_index_dir
    index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_dir))
    logger.info("Indexed %d postings into %s", len(documents), index_dir)


def index_exists() -> bool:
    settings = get_settings()
    index_dir = PROJECT_ROOT / settings.internship_index_dir
    return (index_dir / "index.faiss").exists()


def get_vectorstore() -> FAISS:
    """Loads the saved FAISS index once per process and caches it. Raises
    FileNotFoundError with a clear message if build_index() hasn't been run
    yet - that's a setup error, not something to silently work around."""
    global _vectorstore
    if _vectorstore is None:
        settings = get_settings()
        index_dir = PROJECT_ROOT / settings.internship_index_dir
        if not (index_dir / "index.faiss").exists():
            raise FileNotFoundError(
                f"No internship index found at {index_dir}. Run "
                "`python -m app.services.internship_index` to build it."
            )
        _vectorstore = FAISS.load_local(
            str(index_dir),
            _get_embeddings(),
            allow_dangerous_deserialization=True,  # we wrote this index ourselves
        )
    return _vectorstore


def search_similar_internships(query_text: str, k: int = 5) -> list[dict]:
    """Returns the top-k postings most similar to query_text, each as the
    posting's dict plus a match_score (higher = more similar, 0-1 range)."""
    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search_with_score(query_text, k=k)

    matches = []
    for doc, distance in results:
        # FAISS's default index returns L2 distance (lower = closer); convert
        # to a 0-1 "similarity" score that's more intuitive for API consumers.
        score = 1.0 / (1.0 + distance)
        matches.append({**doc.metadata, "match_score": round(score, 4)})
    return matches


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_index()
