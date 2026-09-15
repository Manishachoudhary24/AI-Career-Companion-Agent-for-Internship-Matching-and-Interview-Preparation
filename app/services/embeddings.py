# ---------------------------------------------------------------------------
# Shared embedding-model loader.
#
# Both FAISS indices in this project (the pre-existing internship-matching
# index and the new Product Knowledge Document index used by the AI
# Assistant chatbot) embed text into the *same* local sentence-transformers
# model (see app.config.Settings.embedding_model). This module loads that
# model exactly once per process and hands the cached instance to whichever
# index needs it, instead of each index loading its own copy.
# ---------------------------------------------------------------------------
from __future__ import annotations

from langchain_huggingface import HuggingFaceEmbeddings

from app.config import get_settings

_embeddings: HuggingFaceEmbeddings | None = None


def get_shared_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        settings = get_settings()
        _embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    return _embeddings
