import getpass
import os

# Must run before app imports so the engine binds to the test database.
# No username in the file: PostgreSQL role defaults to the current OS user.
_test_database_url = os.environ.get("TEST_DATABASE_URL")
if not _test_database_url:
    _test_database_url = f"postgresql+psycopg://{getpass.getuser()}@localhost:5432/fdel_test"
os.environ["DATABASE_URL"] = _test_database_url
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["JWT_SECRET"] = "test-secret-key-at-least-32-bytes-long"
os.environ["DOWNLOAD_RATE_LIMIT"] = "50"
os.environ["DOWNLOAD_RATE_WINDOW_SECONDS"] = "60"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.rate_limit import close_redis, get_redis


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setattr(settings, "storage_path", str(storage))
    monkeypatch.setattr(settings, "max_file_size", 100 * 1024 * 1024)
    monkeypatch.setattr(settings, "user_storage_limit", 500 * 1024 * 1024)
    monkeypatch.setattr(settings, "download_rate_limit", 50)

    close_redis()
    get_redis().flushdb()

    with SessionLocal() as db:
        db.execute(text("TRUNCATE refresh_tokens, files, users RESTART IDENTITY CASCADE"))
        db.commit()

    yield

    close_redis()
    for path in storage.iterdir():
        if path.is_file():
            path.unlink()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_auth_headers(client):
    response = client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "password123"},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
