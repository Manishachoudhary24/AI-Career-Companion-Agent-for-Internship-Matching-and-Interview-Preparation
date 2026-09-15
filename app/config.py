"""
Centralized application configuration.
Reads from environment variables / .env file.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- Database ----
    database_url: str = "postgresql://postgres:postgres@localhost:5432/ai_career_companion"

    # ---- JWT ----
    jwt_secret_key: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    reset_token_expire_minutes: int = 30

    # ---- Groq / LLM ----
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    llm_temperature: float = 0.0
    llm_max_retries: int = 3
    llm_timeout_seconds: int = 60

    # ---- Upload ----
    max_upload_mb: int = 10
    allowed_extensions: tuple[str, ...] = (".pdf", ".docx")
    upload_dir: str = "uploads"
    parsed_dir: str = "parsed"

    # ---- Internship Matching (RAG / Milestone 2) ----
    # Local sentence-transformers model - no API key/cost, runs on CPU.
    # Resumes and internship postings are embedded into this same vector
    # space so semantic similarity search works (see
    # app/services/internship_index.py).
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    internship_data_path: str = "app/data/internships.json"
    internship_index_dir: str = "app/data/faiss_internship_index"
    # Auto-build the FAISS index on startup if it doesn't exist yet, so a
    # fresh clone works out of the box (python -m app.services.internship_index
    # can still be run manually any time internships.json changes).
    auto_build_internship_index: bool = True

    # ---- AI Assistant / Product Knowledge RAG chatbot ----
    # Separate document + FAISS index from the internship matcher above, so
    # rebuilding one never touches the other (see app/services/product_knowledge.py).
    product_knowledge_doc_path: str = "app/data/product_knowledge/product_knowledge.md"
    product_knowledge_index_dir: str = "app/data/faiss_product_knowledge"
    auto_build_product_knowledge_index: bool = True
    # How many recent messages (user + assistant) from the current session
    # are fed back into the LLM prompt as conversation memory.
    chat_history_limit: int = 12
    # How many Product Knowledge Document chunks are retrieved per question.
    chat_rag_top_k: int = 4

    # ---- App ----
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
