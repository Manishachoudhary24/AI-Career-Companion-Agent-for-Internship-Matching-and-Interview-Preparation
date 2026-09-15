"""
FastAPI authentication dependencies.

`get_current_user` is used to protect private endpoints: it decodes the
bearer JWT, rejects blacklisted/revoked tokens (logout support), and loads
the corresponding active user from PostgreSQL.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.models import TokenBlacklist, User
from app.utils.jwt_handler import TokenError, decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token)
    except TokenError:
        raise CREDENTIALS_EXCEPTION

    if payload.get("type") != "access":
        raise CREDENTIALS_EXCEPTION

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if user_id is None or jti is None:
        raise CREDENTIALS_EXCEPTION

    # Reject tokens that were explicitly logged out
    blacklisted = db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first()
    if blacklisted is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    except ValueError:
        raise CREDENTIALS_EXCEPTION

    if user is None:
        raise CREDENTIALS_EXCEPTION
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive.")

    return user


def get_current_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    """Used by /logout to grab the raw jti/exp claims of the presented token."""
    try:
        payload = decode_token(token)
    except TokenError:
        raise CREDENTIALS_EXCEPTION
    if payload.get("type") != "access":
        raise CREDENTIALS_EXCEPTION
    return payload
