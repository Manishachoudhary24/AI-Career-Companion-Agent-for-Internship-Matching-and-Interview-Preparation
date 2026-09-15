"""
AI Career Companion - FastAPI application entrypoint.

Combines:
  Part 1: User Management APIs (register/login/logout/password reset/profile)
  Part 2: Resume Parser API (hybrid Regex + LangChain/Groq LLM pipeline)
  Part 3: Internship Matching API (Milestone 2 RAG pipeline, FAISS vector search)

Run with:
    uvicorn app.main:app --reload

Swagger UI: http://localhost:8000/docs
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.database import init_db
from app.models.schemas import ErrorResponse
from app.routers import auth, career, chat, internships, interview_prep, resume

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("ai_career_companion")

app = FastAPI(
    title="AI Career Companion",
    description=(
        "Production-style FastAPI backend combining JWT user management with "
        "a hybrid Regex + LangChain/Groq LLM resume-parsing pipeline, backed "
        "by PostgreSQL."
    ),
    version="1.0.0",
)

cors_origins = ["*"] if settings.cors_origins.strip() == "*" else [
    o.strip() for o in settings.cors_origins.split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(internships.router)
app.include_router(career.router)
app.include_router(chat.router)
app.include_router(interview_prep.router)


@app.on_event("startup")
def on_startup() -> None:
    logger.info("Starting AI Career Companion (env=%s)", settings.app_env)
    init_db()
    logger.info("Database tables verified/created.")

    if settings.auto_build_internship_index:
        # Best-effort: build the FAISS internship index on first boot if it
        # doesn't exist yet, so a fresh clone works without a manual step.
        # Never blocks startup - GET /internships/match/{id} will raise a
        # clear 500 with instructions if this failed (e.g. no internet
        # access to download the embedding model on first run).
        try:
            from app.services.internship_index import build_index, index_exists

            if not index_exists():
                logger.info("No internship FAISS index found - building one now...")
                build_index()
                logger.info("Internship FAISS index built.")
        except Exception:
            logger.exception(
                "Could not auto-build the internship FAISS index. Run "
                "`python -m app.services.internship_index` manually, or set "
                "AUTO_BUILD_INTERNSHIP_INDEX=false to silence this at startup."
            )

    if settings.auto_build_product_knowledge_index:
        # Same best-effort pattern as the internship index above, but for the
        # AI Assistant's Product Knowledge Document index. This is a
        # completely separate FAISS index/directory - see
        # app/services/product_knowledge.py - so it can never corrupt the
        # internship-matching index built above.
        try:
            from app.services.product_knowledge import build_index as build_product_index
            from app.services.product_knowledge import index_exists as product_index_exists

            if not product_index_exists():
                logger.info("No product-knowledge FAISS index found - building one now...")
                build_product_index()
                logger.info("Product-knowledge FAISS index built.")
        except Exception:
            logger.exception(
                "Could not auto-build the product-knowledge FAISS index. Run "
                "`python -m app.services.product_knowledge` manually, or set "
                "AUTO_BUILD_PRODUCT_KNOWLEDGE_INDEX=false to silence this at startup. "
                "The AI Assistant will still work but without retrieved context "
                "until this index is built."
            )


@app.get("/", tags=["System"], summary="Root - basic API info")
def root() -> dict:
    return {
        "name": "AI Career Companion",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["System"], summary="Liveness/readiness probe")
def health_check() -> dict:
    return {"status": "ok", "model": settings.groq_model}


# --------------------------------------------------------------------------- #
# Centralized error handling -> consistent JSON error envelope
# --------------------------------------------------------------------------- #


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(message=str(exc.detail)).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            message="Validation error.",
            detail=str(exc.errors()),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(message="Internal server error.").model_dump(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
