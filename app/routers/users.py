from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import StorageOut, UserOut
from app.services.files import storage_snapshot

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/me/storage", response_model=StorageOut)
def my_storage(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StorageOut:
    return storage_snapshot(db, user.id)
