from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer, field_validator


def _dump_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_dump_datetime, when_used="json")]


class AuthIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def password_byte_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return value


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: UtcDatetime


class StorageOut(BaseModel):
    used_bytes: int
    limit_bytes: int
    available_bytes: int


class FileOut(BaseModel):
    id: UUID
    filename: str
    size: int
    content_type: str
    share_mode: Literal["link", "code"]
    download_url: str | None
    access_code: str | None
    expires_at: UtcDatetime
    created_at: UtcDatetime


class LinkShareOut(BaseModel):
    filename: str
    size: int
    content_type: str
    sender_email: str
    expires_at: UtcDatetime
    download_url: str


class CodeDownloadIn(BaseModel):
    code: str = Field(min_length=8, max_length=8)
    password: str = Field(min_length=4, max_length=72)

    @field_validator("code")
    @classmethod
    def alphanumeric_code(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 8 or not cleaned.isalnum():
            raise ValueError("Code must be 8 letters or digits")
        return cleaned


class FilePage(BaseModel):
    items: list[FileOut]
    page: int
    limit: int
    total: int


class HistoryItem(BaseModel):
    id: UUID
    filename: str
    size: int
    created_at: UtcDatetime
    status: Literal["expired", "deleted"]


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    page: int
    limit: int
    total: int
