import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.models import User
from app.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "unauthorized", "Authentication required")
    payload = decode_token(credentials.credentials, "access")
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise AppError(401, "invalid_token", "Invalid token") from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError(401, "unauthorized", "Authentication required")
    return user
