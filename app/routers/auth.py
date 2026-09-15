"""
Part 1 - User Management APIs.

POST   /register
POST   /login
POST   /logout
POST   /forgot-password
POST   /reset-password
POST   /change-password
GET    /profile
PUT    /profile
DELETE /profile
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import get_db
from app.models.models import PasswordResetToken, TokenBlacklist, User
from app.models.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    MessageResponse,
    ProfileUpdate,
    ResetPasswordRequest,
    Token,
    UserLogin,
    UserOut,
    UserRegister,
)
from app.utils.jwt_handler import TokenError, create_access_token, create_password_reset_token, decode_token
from app.utils.password import hash_password, verify_password
from app.utils.security import get_current_token_payload, get_current_user

logger = logging.getLogger("ai_career_companion.auth")
settings = get_settings()

router = APIRouter(tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> UserOut:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Email is already registered.")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        phone_number=payload.phone_number,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("New user registered: %s", user.email)
    return user


@router.post("/login", response_model=Token, summary="Log in and obtain a JWT access token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:

    # Swagger OAuth2 sends username; we treat it as the user's email.
    user = db.query(User).filter(User.email == form_data.username).first()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    token, _jti, expires_in = create_access_token(subject=str(user.id))

    return Token(
        access_token=token,
        expires_in_minutes=expires_in,
    )


@router.post("/logout", response_model=MessageResponse, summary="Log out (revoke the current access token)")
def logout(
    payload: dict = Depends(get_current_token_payload),
    db: Session = Depends(get_db),
) -> MessageResponse:
    jti = payload["jti"]
    exp_ts = payload["exp"]
    expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)

    already = db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first()
    if already is None:
        db.add(TokenBlacklist(jti=jti, expires_at=expires_at))
        db.commit()

    return MessageResponse(message="Successfully logged out.")


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request a password reset token",
)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    # Always respond the same way whether or not the email exists, to avoid
    # leaking which emails are registered. Only issue a real token if found.
    generic_message = "If that email is registered, a password reset token has been issued."

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No account found with that email.")

    token, expires_at, expires_in = create_password_reset_token(subject=str(user.id))
    db.add(PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at))
    db.commit()

    # NOTE: No SMTP/email provider is configured in this project. In a real
    # deployment this token would be emailed to the user rather than
    # returned in the response. It is logged + returned here purely for
    # local development/testing convenience.
    logger.info("Password reset token issued for %s: %s", user.email, token)

    return ForgotPasswordResponse(message=generic_message, reset_token=token, expires_in_minutes=expires_in)


@router.post("/reset-password", response_model=MessageResponse, summary="Reset password using a reset token")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    try:
        claims = decode_token(payload.token)
    except TokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired reset token.")

    if claims.get("type") != "reset":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid reset token type.")

    record = db.query(PasswordResetToken).filter(PasswordResetToken.token == payload.token).first()
    if record is None or record.used:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reset token is invalid or already used.")

    if record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reset token has expired.")

    user = db.query(User).filter(User.id == record.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.hashed_password = hash_password(payload.new_password)
    record.used = True
    db.commit()

    return MessageResponse(message="Password has been reset successfully. Please log in with your new password.")


@router.post("/change-password", response_model=MessageResponse, summary="Change password (authenticated)")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect.")

    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return MessageResponse(message="Password changed successfully.")


@router.get("/profile", response_model=UserOut, summary="Get the current user's profile")
def get_profile(current_user: User = Depends(get_current_user)) -> UserOut:
    return current_user


@router.put("/profile", response_model=UserOut, summary="Update the current user's profile")
def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.phone_number is not None:
        current_user.phone_number = payload.phone_number

    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/profile", response_model=MessageResponse, summary="Delete the current user's account")
def delete_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    db.delete(current_user)
    db.commit()
    return MessageResponse(message="User account deleted successfully.")
