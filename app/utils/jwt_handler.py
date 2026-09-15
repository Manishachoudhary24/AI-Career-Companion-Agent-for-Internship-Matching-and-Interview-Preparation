"""
JWT access-token and password-reset-token creation/decoding, using python-jose.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()


class TokenError(Exception):
    pass


def create_access_token(subject: str) -> tuple[str, str, int]:
    """
    Create a signed JWT access token for the given subject (user id).
    Returns (token, jti, expires_in_minutes).
    """
    jti = str(uuid.uuid4())
    expire_minutes = settings.access_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

    payload: dict[str, Any] = {
        "sub": subject,
        "jti": jti,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expire_minutes


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as exc:
        raise TokenError(f"Invalid or expired token: {exc}") from exc


def create_password_reset_token(subject: str) -> tuple[str, datetime, int]:
    """
    Create a signed JWT reset token (separate `type` claim so it can't be
    reused as an access token). Returns (token, expires_at, expires_in_minutes).
    """
    expire_minutes = settings.reset_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

    payload: dict[str, Any] = {
        "sub": subject,
        "jti": str(uuid.uuid4()),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "reset",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expire, expire_minutes
