"""
AI Assistant / Product Chatbot API.

POST   /chat/sessions                          - start a new chat session
GET    /chat/sessions                          - list the current user's sessions
GET    /chat/sessions/{session_id}/messages    - list a session's messages
POST   /chat/sessions/{session_id}/messages    - send a message, get an AI reply
DELETE /chat/sessions/{session_id}             - delete a session

Every endpoint requires authentication and verifies the session belongs to
the requesting user (404, not 403, for someone else's session - same
ownership pattern used by /internships/match/{resume_id}). Conversation
history is always scoped to user_id + session_id, so users never see each
other's chats.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.models import ChatMessage, ChatSession, User
from app.models.schemas import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSendResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ErrorResponse,
)
from app.services.chat_service import ChatServiceError, default_session_title, generate_reply
from app.utils.security import get_current_user

logger = logging.getLogger("ai_career_companion.chat_router")

router = APIRouter(prefix="/chat", tags=["AI Assistant"])


def _get_owned_session(session_id: uuid.UUID, user: User, db: Session) -> ChatSession:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
    return session


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new AI Assistant chat session",
)
def create_session(
    payload: ChatSessionCreate | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSession:
    session = ChatSession(
        user_id=current_user.id,
        title=(payload.title if payload and payload.title else "New chat"),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    summary="List the current user's chat sessions",
)
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a chat session and its messages",
)
def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    session = _get_owned_session(session_id, current_user, db)
    db.delete(session)
    db.commit()


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageResponse],
    summary="List a chat session's messages",
)
def list_messages(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessage]:
    _get_owned_session(session_id, current_user, db)
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatSendResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Send a message to the AI Assistant and get a RAG-grounded reply",
)
def send_message(
    session_id: uuid.UUID,
    payload: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSendResponse:
    session = _get_owned_session(session_id, current_user, db)

    text = (payload.message or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty.")

    user_msg = ChatMessage(
        session_id=session.id,
        user_id=current_user.id,
        role="user",
        message=text,
    )
    db.add(user_msg)
    db.flush()

    try:
        answer, sources = generate_reply(db, session, text)
    except ChatServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Unexpected AI Assistant failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The AI Assistant is temporarily unavailable. Please try again.",
        ) from exc

    assistant_msg = ChatMessage(
        session_id=session.id,
        user_id=current_user.id,
        role="assistant",
        message=answer,
        sources=sources or None,
    )
    db.add(assistant_msg)

    # First message in a session -> auto-title it from the question.
    if session.title == "New chat":
        session.title = default_session_title(text)

    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)

    return ChatSendResponse(user_message=user_msg, assistant_message=assistant_msg)
