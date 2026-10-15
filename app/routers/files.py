from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import FileOut, FilePage, HistoryPage
from app.services.files import (
    create_stored_file,
    delete_active_file,
    get_active_file,
    list_active_files,
    list_history,
)

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", response_model=FileOut, status_code=201)
def upload_file(
    file: UploadFile = File(...),
    expires_in: int | None = Form(default=None),
    share_mode: str = Form(default="link"),
    share_password: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileOut:
    return create_stored_file(db, user, file, expires_in, share_mode, share_password)


@router.get("", response_model=FilePage)
def list_files(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FilePage:
    return list_active_files(db, user, page, limit)


@router.get("/history", response_model=HistoryPage)
def file_history(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryPage:
    return list_history(db, user, page, limit)


@router.get("/{file_id}", response_model=FileOut)
def file_details(
    file_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileOut:
    return get_active_file(db, user, file_id)


@router.delete("/{file_id}", status_code=204)
def delete_file(
    file_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    delete_active_file(db, user, file_id)
