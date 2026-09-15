# ---------------------------------------------------------------------------
# AI ASSISTANT / PRODUCT CHATBOT - business logic.
#
# Flow (see app/services/product_knowledge.py for the retrieval half):
#   system instructions + retrieved Product Knowledge chunks
#   + recent conversation history + current question -> Groq LLM -> answer
#
# Reuses the project's existing Groq configuration (app.config.Settings:
# groq_api_key / groq_model) - no second LLM configuration system.
# ---------------------------------------------------------------------------
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.models import ChatMessage, ChatSession
from app.services.product_knowledge import retrieve_relevant_chunks

logger = logging.getLogger("ai_career_companion.chat")
settings = get_settings()

SYSTEM_PROMPT = """You are the AI Product Assistant for AI Career Companion.

Your role is to help users understand and use the AI Career Companion application.

For greetings and questions about your identity, role, or purpose, respond naturally and briefly based on your role as the AI Product Assistant.

For questions about AI Career Companion, answer using the retrieved product documentation and relevant conversation history.

Do not invent product features, technologies, workflows, APIs, or implementation details.

Do not answer unrelated general-knowledge questions.

Be concise, clear, and helpful.

When explaining how to perform an action, provide step-by-step instructions."""


NO_CONTEXT_FALLBACK = (
    "Sorry, I can assist you only with questions related to the "
    "AI Career Companion product and its features."
)

def _is_casual_conversation(question: str) -> bool:
    question = (question or "").lower().strip()

    casual_questions = {
        "hi",
        "hello",
        "hey",
        "hi there",
        "hello there",
        "hey there",
        "who are you",
        "what are you",
        "what do you do",
        "what can you do",
        "what is your purpose",
        "what's your purpose",
        "what is your role",
        "what's your role",
        "who are you?",
        "what are you?",
        "what do you do?",
        "what can you do?",
        "what is your purpose?",
        "what's your purpose?",
        "what is your role?",
        "what's your role?",
    }

    return question in casual_questions

def _is_product_related(user_question: str) -> bool:
    question = (user_question or "").lower().strip()

    if not question:
        return False

    product_keywords = [
        "ai career companion",
        "career companion",
        "resume",
        "cv",
        "internship",
        "internships",
        "profile",
        "skill",
        "skills",
        "experience",
        "education",
        "project",
        "projects",
        "cover letter",
        "job",
        "jobs",
        "application",
        "applied",
        "matching",
        "match",
        "dashboard",
        "assistant",
        "chatbot",
        "chat",
        "career",
        "recommendation",
        "generate",
        "upload",
        "parse",
        "parsing",
        "personal details",
        "profile photo",
        "achievement",
        "achievements",
    ]

    return any(keyword in question for keyword in product_keywords)

class ChatServiceError(Exception):
    """Raised for chatbot failures that should surface as a clean API error
    rather than a raw exception (missing API key, empty LLM response, etc.)."""


def _recent_history(db: Session, session_id, limit: int) -> list[ChatMessage]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))



def generate_reply(db: Session, session: ChatSession, user_question: str) -> tuple[str, list[str]]:
    """Runs the RAG + memory pipeline and returns (answer_text, sources).
    Raises ChatServiceError on any failure that should be reported to the
    caller as an error rather than silently degraded."""

    if not settings.groq_api_key:
        raise ChatServiceError(
            "The AI Assistant is not configured yet: GROQ_API_KEY is missing on the server."
        )
        
        # ---- 0. Handle casual conversation -------------------------------
    if _is_casual_conversation(user_question):
        casual_messages = [
            {
                "role": "system",
                "content": (
                    "You are the AI Product Assistant for AI Career Companion. "
                    "Respond briefly and naturally to greetings or questions "
                    "about your identity, role, or purpose. "
                    "Do not discuss unrelated general topics."
                ),
            },
            {
                "role": "user",
                "content": user_question,
            },
        ]

        try:
            from groq import Groq

            client = Groq(api_key=settings.groq_api_key)
            result = client.chat.completions.create(
                model=settings.groq_model,
                messages=casual_messages,
                temperature=settings.llm_temperature,
            )

            answer = (result.choices[0].message.content or "").strip()

            if answer:
                return answer, []

        except Exception:
            logger.exception("Casual conversation response failed")

        return (
            "Hello! I’m the AI Product Assistant for AI Career Companion. "
            "I can help you understand and use the product and its features.",
            [],
        )

    # ---- 1. Product scope check --------------------------------------
    if not _is_product_related(user_question):
        return NO_CONTEXT_FALLBACK, []
    

    # ---- 1. RAG retrieval (never raises - degrades to no context) --------
    chunks = retrieve_relevant_chunks(user_question, k=settings.chat_rag_top_k)
    sources = sorted({c["source"] for c in chunks})

    if chunks:
        context_block = "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)
    else:
        context_block = (
            "(No matching sections were found in the Product Knowledge Document for this question.)"
        )

    # ---- 2. Conversation memory (recent turns of THIS session only) ------
    history = _recent_history(db, session.id, settings.chat_history_limit)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({
        "role": "system",
        "content": (
            "Retrieved product documentation context (use this as your primary source; "
            f"if it doesn't answer the question, say: \"{NO_CONTEXT_FALLBACK}\"):\n\n{context_block}"
        ),
    })
    for m in history:
        role = "assistant" if m.role == "assistant" else "user"
        messages.append({"role": role, "content": m.message})
    messages.append({"role": "user", "content": user_question})

    # ---- 3. Call the existing Groq integration ----------------------------
    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)
        result = client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            temperature=settings.llm_temperature,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("AI Assistant LLM call failed")
        message = str(exc)
        if "rate" in message.lower() and "limit" in message.lower():
            raise ChatServiceError("The AI Assistant is rate-limited right now. Please try again shortly.") from exc
        raise ChatServiceError(f"The AI Assistant failed to generate a response: {exc}") from exc

    try:
        answer = (result.choices[0].message.content or "").strip()
    except (AttributeError, IndexError) as exc:
        raise ChatServiceError("The AI Assistant returned an unexpected response.") from exc

    if not answer:
        raise ChatServiceError("The AI Assistant returned an empty response. Please try again.")

    return answer, (sources if chunks else [])


def default_session_title(first_message: str) -> str:
    text = (first_message or "New chat").strip().replace("\n", " ")
    return (text[:60] + "…") if len(text) > 60 else (text or "New chat")

