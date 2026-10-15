import secrets
import string
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.config import (
    ALLOWED_EXPIRATION_MINUTES,
    BLOCKED_EXTENSIONS,
    DEFAULT_EXPIRATION_MINUTES,
    settings,
)
from app.errors import AppError
from app.models import StoredFile, User, utcnow
from app.schemas import FileOut, FilePage, HistoryItem, HistoryPage, StorageOut
from app.security import hash_password, verify_password

SHARE_LINK = "link"
SHARE_CODE = "code"
SHARE_MODES = {SHARE_LINK, SHARE_CODE}
ACCESS_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _not_found() -> AppError:
    return AppError(404, "file_not_found", "File not found")


def clean_filename(filename: str | None) -> str:
    name = Path(filename or "file").name.replace("\x00", "").replace("\r", "").replace("\n", "").strip()
    if not name or name in {".", ".."}:
        name = "file"
    return name[:255]


def extension_blocked(filename: str) -> bool:
    return Path(filename).suffix.lower() in BLOCKED_EXTENSIONS


def resolve_storage_path(storage_key: str) -> Path:
    root = settings.storage_dir.resolve()
    path = (root / storage_key).resolve()
    if path.parent != root:
        raise _not_found()
    return path


def active_usage(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> int:
    value = db.scalar(
        select(func.coalesce(func.sum(StoredFile.size), 0)).where(
            *_active_filters(user_id, now or utcnow())
        )
    )
    return int(value)


def purge_expired_files(db: Session) -> int:
    """Remove expired files from disk once; rows stay for history."""
    now = utcnow()
    rows = db.scalars(
        select(StoredFile).where(
            StoredFile.deleted_at.is_(None),
            StoredFile.purged_at.is_(None),
            StoredFile.expires_at <= now,
        )
    ).all()
    for row in rows:
        try:
            resolve_storage_path(row.storage_key).unlink(missing_ok=True)
        except AppError:
            pass
        row.purged_at = now
    if rows:
        db.commit()
    return len(rows)


def storage_snapshot(db: Session, user_id: uuid.UUID) -> StorageOut:
    purge_expired_files(db)
    used = active_usage(db, user_id)
    limit = settings.user_storage_limit
    return StorageOut(used_bytes=used, limit_bytes=limit, available_bytes=max(limit - used, 0))


def _write_limited(source, dest: Path, max_size: int) -> int:
    size = 0
    try:
        with dest.open("wb") as output:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_size:
                    raise AppError(413, "file_too_large", "File exceeds the maximum allowed size")
                output.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return size


def _allocate_unique(
    db: Session,
    column: InstrumentedAttribute[str],
    generate: Callable[[], str],
    attempts: int = 10,
) -> str:
    for _ in range(attempts):
        value = generate()
        if db.scalar(select(StoredFile.id).where(column == value)) is None:
            return value
    raise AppError(500, "token_generation_failed", "Could not allocate a unique identifier")


def _generate_access_code() -> str:
    return "".join(secrets.choice(ACCESS_CODE_ALPHABET) for _ in range(8))


def _to_file_out(record: StoredFile) -> FileOut:
    is_link = record.share_mode == SHARE_LINK
    return FileOut(
        id=record.id,
        filename=record.original_name,
        size=record.size,
        content_type=record.content_type,
        share_mode=record.share_mode,
        download_url=f"/d/{record.download_token}" if is_link else None,
        access_code=None if is_link else record.access_code,
        expires_at=record.expires_at,
        created_at=record.created_at,
    )


def _validate_share_options(share_mode: str | None, share_password: str | None) -> tuple[str, str | None]:
    mode = (share_mode or SHARE_LINK).strip().lower()
    if mode not in SHARE_MODES:
        raise AppError(400, "unsupported_share_mode", "share_mode must be link or code")
    if mode == SHARE_LINK:
        return mode, None
    password = (share_password or "").strip()
    if len(password) < 4 or len(password.encode("utf-8")) > 72:
        raise AppError(400, "share_password_invalid", "Share password must be 4 to 72 characters")
    return mode, password


def _validate_expiration(expires_in: int | None) -> int:
    minutes = DEFAULT_EXPIRATION_MINUTES if expires_in is None else expires_in
    if minutes not in ALLOWED_EXPIRATION_MINUTES:
        raise AppError(400, "unsupported_expiration", "expires_in must be 5, 10, or 15")
    return minutes


def _ensure_quota(db: Session, user_id: uuid.UUID, size: int, now: datetime) -> None:
    locked = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if locked is None:
        raise AppError(401, "unauthorized", "Authentication required")
    if active_usage(db, user_id, now) + size > settings.user_storage_limit:
        raise AppError(400, "quota_exceeded", "Storage quota exceeded")


def create_stored_file(
    db: Session,
    user: User,
    upload: UploadFile,
    expires_in: int | None,
    share_mode: str = SHARE_LINK,
    share_password: str | None = None,
) -> FileOut:
    file_id = uuid.uuid4()
    part_path = settings.storage_dir / f"{file_id}.uploading"
    final_path = settings.storage_dir / str(file_id)
    committed = False

    try:
        mode, password = _validate_share_options(share_mode, share_password)
        minutes = _validate_expiration(expires_in)
        original_name = clean_filename(upload.filename)
        if extension_blocked(original_name):
            raise AppError(400, "file_type_blocked", "This file type is not allowed")

        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        size = _write_limited(upload.file, part_path, settings.max_file_size)
        now = utcnow()
        _ensure_quota(db, user.id, size, now)

        is_code = mode == SHARE_CODE
        record = StoredFile(
            id=file_id,
            owner_id=user.id,
            original_name=original_name,
            storage_key=str(file_id),
            size=size,
            content_type=(upload.content_type or "application/octet-stream")[:255],
            download_token=_allocate_unique(db, StoredFile.download_token, lambda: secrets.token_urlsafe(9)),
            share_mode=mode,
            access_code=_allocate_unique(db, StoredFile.access_code, _generate_access_code) if is_code else None,
            access_password_hash=hash_password(password) if is_code else None,
            expires_at=now + timedelta(minutes=minutes),
            created_at=now,
        )
        part_path.replace(final_path)
        db.add(record)
        db.commit()
        committed = True
        db.refresh(record)
        return _to_file_out(record)
    except Exception:
        if not committed:
            db.rollback()
            part_path.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
        raise
    finally:
        upload.file.close()


def _active_filters(user_id: uuid.UUID, now: datetime) -> tuple:
    return (
        StoredFile.owner_id == user_id,
        StoredFile.deleted_at.is_(None),
        StoredFile.expires_at > now,
    )


def _history_filters(user_id: uuid.UUID, now: datetime) -> tuple:
    return (
        StoredFile.owner_id == user_id,
        or_(StoredFile.deleted_at.is_not(None), StoredFile.expires_at <= now),
    )


def _paginate(db: Session, filters: tuple, page: int, limit: int) -> tuple[list[StoredFile], int]:
    total = db.scalar(select(func.count()).select_from(StoredFile).where(*filters)) or 0
    rows = db.scalars(
        select(StoredFile)
        .where(*filters)
        .order_by(StoredFile.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return list(rows), int(total)


def list_active_files(db: Session, user: User, page: int, limit: int) -> FilePage:
    purge_expired_files(db)
    rows, total = _paginate(db, _active_filters(user.id, utcnow()), page, limit)
    return FilePage(items=[_to_file_out(row) for row in rows], page=page, limit=limit, total=total)


def list_history(db: Session, user: User, page: int, limit: int) -> HistoryPage:
    purge_expired_files(db)
    rows, total = _paginate(db, _history_filters(user.id, utcnow()), page, limit)
    items = [
        HistoryItem(
            id=row.id,
            filename=row.original_name,
            size=row.size,
            created_at=row.created_at,
            status="deleted" if row.deleted_at is not None else "expired",
        )
        for row in rows
    ]
    return HistoryPage(items=items, page=page, limit=limit, total=total)


def _get_owned_active(db: Session, user: User, file_id: uuid.UUID) -> StoredFile:
    record = db.get(StoredFile, file_id)
    if (
        record is None
        or record.owner_id != user.id
        or record.deleted_at is not None
        or record.expires_at <= utcnow()
    ):
        raise _not_found()
    return record


def get_active_file(db: Session, user: User, file_id: uuid.UUID) -> FileOut:
    return _to_file_out(_get_owned_active(db, user, file_id))


def delete_active_file(db: Session, user: User, file_id: uuid.UUID) -> None:
    record = _get_owned_active(db, user, file_id)
    resolve_storage_path(record.storage_key).unlink(missing_ok=True)
    record.deleted_at = utcnow()
    db.commit()


def _ready_file(db: Session, record: StoredFile | None, share_mode: str) -> tuple[StoredFile, Path]:
    if record is None or record.deleted_at is not None or record.share_mode != share_mode:
        raise _not_found()
    if record.expires_at <= utcnow():
        purge_expired_files(db)
        raise AppError(410, "file_expired", "File has expired")
    path = resolve_storage_path(record.storage_key)
    if not path.is_file():
        raise _not_found()
    return record, path


def _by_token(db: Session, token: str) -> StoredFile | None:
    return db.scalar(select(StoredFile).where(StoredFile.download_token == token))


def get_public_file(db: Session, token: str) -> tuple[StoredFile, Path]:
    return _ready_file(db, _by_token(db, token), SHARE_LINK)


def get_link_share_info(db: Session, token: str) -> tuple[StoredFile, str]:
    record, _ = _ready_file(db, _by_token(db, token), SHARE_LINK)
    sender_email = db.scalar(select(User.email).where(User.id == record.owner_id))
    if sender_email is None:
        raise _not_found()
    return record, sender_email


def get_file_by_code(db: Session, code: str, password: str) -> tuple[StoredFile, Path]:
    record = db.scalar(select(StoredFile).where(StoredFile.access_code == code))
    record, path = _ready_file(db, record, SHARE_CODE)
    if not record.access_password_hash or not verify_password(password, record.access_password_hash):
        raise AppError(401, "invalid_share_password", "Invalid code or password")
    return record, path
