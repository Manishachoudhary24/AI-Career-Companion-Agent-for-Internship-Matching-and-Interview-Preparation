# ---------------------------------------------------------------------------
# PRODUCT KNOWLEDGE RAG INDEX - powers the AI Assistant chatbot.
#
# This mirrors the shape of app/services/internship_index.py on purpose (same
# embedding model, same "build once / load cached / search" pattern) but is
# kept as a fully separate module, writing to a fully separate FAISS index
# directory (settings.product_knowledge_index_dir), so rebuilding this index
# can never overwrite or corrupt the existing internship-matching index.
#
# Source document: app/data/product_knowledge/product_knowledge.md, split
# into one chunk per "##" section. Each chunk's heading doubles as the
# human-readable "source" shown alongside a chatbot answer.
# ---------------------------------------------------------------------------
from __future__ import annotations

import logging
import re
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.config import get_settings
from app.services.embeddings import get_shared_embeddings

logger = logging.getLogger("ai_career_companion.product_knowledge")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_vectorstore: FAISS | None = None

_HEADER_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _source_path() -> Path:
    settings = get_settings()
    return PROJECT_ROOT / settings.product_knowledge_doc_path


def _index_dir() -> Path:
    settings = get_settings()
    return PROJECT_ROOT / settings.product_knowledge_index_dir


def load_chunks() -> list[dict]:
    """Splits the Product Knowledge Document into one chunk per `##`
    section. Returns a list of {"title": str, "text": str} dicts."""
    path = _source_path()
    raw = path.read_text(encoding="utf-8")

    matches = list(_HEADER_RE.finditer(raw))
    chunks: list[dict] = []
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[start:end].strip()
        if body:
            chunks.append({"title": title, "text": f"{title}\n{body}"})
    return chunks


def build_index() -> None:
    """(Re)builds the Product Knowledge FAISS index from product_knowledge.md.
    Safe to re-run any time the document is edited; never touches the
    internship-matching index (different directory, different function)."""
    chunks = load_chunks()
    documents = [
        Document(page_content=c["text"], metadata={"source": c["title"]})
        for c in chunks
    ]

    embeddings = get_shared_embeddings()
    vectorstore = FAISS.from_documents(documents, embeddings)

    index_dir = _index_dir()
    index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_dir))
    logger.info("Indexed %d product-knowledge chunks into %s", len(documents), index_dir)


def index_exists() -> bool:
    return (_index_dir() / "index.faiss").exists()


def get_vectorstore() -> FAISS:
    global _vectorstore
    if _vectorstore is None:
        index_dir = _index_dir()
        if not (index_dir / "index.faiss").exists():
            raise FileNotFoundError(
                f"No product-knowledge index found at {index_dir}. Run "
                "`python -m app.services.product_knowledge` to build it."
            )
        _vectorstore = FAISS.load_local(
            str(index_dir),
            get_shared_embeddings(),
            allow_dangerous_deserialization=True,  # we wrote this index ourselves
        )
    return _vectorstore


def retrieve_relevant_chunks(query: str, k: int = 4) -> list[dict]:
    """Returns up to k {"source": str, "text": str} chunks most relevant to
    query. Returns [] (rather than raising) if the index/query is unusable,
    so a RAG retrieval failure degrades the chatbot gracefully instead of
    crashing the request - the LLM is instructed to say it doesn't have
    enough information when no context is retrieved."""
    query = (query or "").strip()
    if not query:
        return []
    try:
        vectorstore = get_vectorstore()
        results = vectorstore.similarity_search_with_score(query, k=k)
    except FileNotFoundError:
        logger.warning("Product-knowledge index missing; chatbot will run without RAG context.")
        return []
    except Exception:
        logger.exception("Product-knowledge retrieval failed")
        return []

    return [
        {"source": doc.metadata.get("source", "Product Knowledge Document"), "text": doc.page_content}
        for doc, score in results
        if score <= 1.0
    ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_index()
