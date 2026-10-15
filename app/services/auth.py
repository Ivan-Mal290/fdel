import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import RefreshToken, User
from app.schemas import TokenPair
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def _issue_tokens(db: Session, user: User) -> TokenPair:
    access_token = create_access_token(user.id)
    refresh_token, jti, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at))
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


def register_user(db: Session, email: str, password: str) -> TokenPair:
    user = User(id=uuid.uuid4(), email=email, password_hash=hash_password(password), is_active=True)
    db.add(user)
    try:
        db.flush()
        tokens = _issue_tokens(db, user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", "") or ""
        if "email" not in constraint:
            raise
        raise AppError(409, "email_taken", "An account with this email already exists") from exc
    return tokens


def login_user(db: Session, email: str, password: str) -> TokenPair:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Invalid email or password")
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def refresh_session(db: Session, refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token, "refresh")
    jti = payload.get("jti")
    if not jti:
        raise AppError(401, "invalid_token", "Invalid token")

    row = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti).with_for_update())
    now = datetime.now(timezone.utc)
    if (
        row is None
        or row.revoked_at is not None
        or row.expires_at <= now
        or str(row.user_id) != payload["sub"]
    ):
        raise AppError(401, "invalid_token", "Invalid token")

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise AppError(401, "invalid_token", "Invalid token")

    row.revoked_at = now
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def logout_session(db: Session, refresh_token: str) -> None:
    payload = decode_token(refresh_token, "refresh")
    jti = payload.get("jti")
    if not jti:
        raise AppError(401, "invalid_token", "Invalid token")

    row = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti).with_for_update())
    if row is None or str(row.user_id) != payload["sub"]:
        raise AppError(401, "invalid_token", "Invalid token")
    if row.revoked_at is not None:
        return

    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
