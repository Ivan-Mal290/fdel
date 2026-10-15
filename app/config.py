from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

BLOCKED_EXTENSIONS = frozenset(
    {
        ".exe",
        ".msi",
        ".bat",
        ".cmd",
        ".com",
        ".scr",
        ".ps1",
        ".dmg",
        ".pkg",
        ".app",
    }
)
ALLOWED_EXPIRATION_MINUTES = frozenset({5, 10, 15})
DEFAULT_EXPIRATION_MINUTES = 15


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://uk@localhost:5432/fdel"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "local-dev-jwt-secret-at-least-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_minutes: int = 60 * 24 * 7
    storage_path: str = "./storage"
    max_file_size: int = 100 * 1024 * 1024
    user_storage_limit: int = 500 * 1024 * 1024
    download_rate_limit: int = 50
    download_rate_window_seconds: int = 60
    public_base_url: str = "http://127.0.0.1:8000"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )

    @property
    def storage_dir(self) -> Path:
        path = Path(self.storage_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
