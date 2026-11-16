import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import PasswordResetToken, User
from ..schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    UserCreate,
    UserResponse,
)
from ..security import (
    create_access_token,
    create_password_reset_token,
    get_current_user,
    hash_password,
    hash_password_reset_token,
    verify_password,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


def send_password_reset_email(email: str, reset_url: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        raise RuntimeError("SMTP email settings are not configured")
    message = EmailMessage()
    message["Subject"] = "Reset your SyncBoard password"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = email
    message.set_content(
        "We received a request to reset your SyncBoard password.\n\n"
        f"Use this link within {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes:\n{reset_url}\n\n"
        "If you did not request this, you can safely ignore this email."
    )
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(email=email, username=payload.username, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = LoginRequest.model_validate(await request.json())
    else:
        form = await request.form()
        payload = LoginRequest(email=str(form.get("username", "")), password=str(form.get("password", "")))
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        raise HTTPException(
            status_code=503,
            detail="Password reset email is not configured on this server",
        )
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is not None:
        raw_token, token_hash = create_password_reset_token()
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
        db.add(reset_token)
        db.commit()
        reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/?reset_token={raw_token}"
        try:
            await run_in_threadpool(send_password_reset_email, user.email, reset_url)
        except (OSError, smtplib.SMTPException, RuntimeError):
            db.delete(reset_token)
            db.commit()
            raise HTTPException(status_code=503, detail="Unable to send password reset email")
    return {"message": "If an account exists for that email, a reset link has been sent"}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    reset_token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_password_reset_token(payload.token),
            PasswordResetToken.used_at.is_(None),
        )
    )
    if reset_token is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    reset_token.user.hashed_password = hash_password(payload.password)
    reset_token.used_at = datetime.now(timezone.utc)
    for token in reset_token.user.password_reset_tokens:
        if token.used_at is None:
            token.used_at = reset_token.used_at
    db.commit()
    return {"message": "Password has been reset successfully"}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different")
    current_user.hashed_password = hash_password(payload.new_password)
    now = datetime.now(timezone.utc)
    for reset_token in current_user.password_reset_tokens:
        if reset_token.used_at is None:
            reset_token.used_at = now
    db.commit()
    return {"message": "Password changed successfully"}
