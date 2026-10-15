from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal
from app.rate_limit import get_redis

settings = get_settings()


def _upload(client, headers, name="notes.txt", content=b"hello file", **data):
    return client.post(
        "/files",
        files={"file": (name, content, "text/plain")},
        data=data,
        headers=headers,
    )


def test_upload_requires_auth(client):
    response = _upload(client, headers=None)
    assert response.status_code == 401


def test_successful_link_upload_and_download(client, auth_headers):
    uploaded = _upload(client, auth_headers, name="../../photo.jpg", content=b"image-bytes")
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["filename"] == "photo.jpg"
    assert body["share_mode"] == "link"
    assert body["download_url"].startswith("/d/")
    assert body["access_code"] is None
    assert body["size"] == len(b"image-bytes")
    assert body["expires_at"].endswith("Z")

    storage_path = settings.storage_dir / body["id"]
    assert storage_path.is_file()

    landing = client.get(body["download_url"])
    assert landing.status_code == 200
    assert "text/html" in landing.headers["content-type"]
    assert "owner@example.com sent you a file" in landing.text
    assert "photo.jpg" in landing.text
    assert b"image-bytes" not in landing.content

    downloaded = client.get(body["download_url"] + "/download")
    assert downloaded.status_code == 200
    assert downloaded.content == b"image-bytes"


def test_upload_validations(client, auth_headers):
    blocked = _upload(client, auth_headers, name="run.EXE", content=b"MZ")
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "file_type_blocked"

    bad_exp = _upload(client, auth_headers, expires_in="30")
    assert bad_exp.status_code == 400
    assert bad_exp.json()["code"] == "unsupported_expiration"

    settings.max_file_size = 4
    too_big = _upload(client, auth_headers, content=b"12345")
    assert too_big.status_code == 413
    assert too_big.json()["code"] == "file_too_large"


def test_quota_and_storage(client, auth_headers):
    empty = client.get("/users/me/storage", headers=auth_headers)
    assert empty.status_code == 200
    assert empty.json() == {
        "used_bytes": 0,
        "limit_bytes": 500 * 1024 * 1024,
        "available_bytes": 500 * 1024 * 1024,
    }

    settings.user_storage_limit = 6
    first = _upload(client, auth_headers, name="q1.txt", content=b"1234")
    second = _upload(client, auth_headers, name="q2.txt", content=b"1234")
    assert first.status_code == 201
    assert second.status_code == 400
    assert second.json()["code"] == "quota_exceeded"
    used = client.get("/users/me/storage", headers=auth_headers).json()["used_bytes"]
    assert used == 4


def test_code_share_mode(client, auth_headers):
    missing_password = _upload(client, auth_headers, share_mode="code")
    assert missing_password.status_code == 400
    assert missing_password.json()["code"] == "share_password_invalid"

    uploaded = _upload(
        client,
        auth_headers,
        name="secret.txt",
        content=b"code-mode",
        share_mode="code",
        share_password="secret",
    )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["share_mode"] == "code"
    assert body["download_url"] is None
    assert len(body["access_code"]) == 8
    assert body["access_code"].isalnum()

    with SessionLocal() as db:
        token = db.execute(
            text("SELECT download_token FROM files WHERE id = :id"),
            {"id": body["id"]},
        ).scalar()
    assert client.get(f"/d/{token}").status_code == 404
    assert client.get(f"/d/{token}/download").status_code == 404

    bad = client.post("/d/code", json={"code": body["access_code"], "password": "wrong"})
    assert bad.status_code == 401
    assert bad.json()["code"] == "invalid_share_password"

    good = client.post(
        "/d/code",
        json={"code": body["access_code"].lower(), "password": "secret"},
    )
    assert good.status_code == 200
    assert good.content == b"code-mode"


def test_manage_own_files_and_foreign_access(client, auth_headers, other_auth_headers):
    uploaded = _upload(client, auth_headers, name="mine.txt", content=b"private")
    file_id = uploaded.json()["id"]
    link = uploaded.json()["download_url"]

    listed = client.get("/files", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    details = client.get(f"/files/{file_id}", headers=auth_headers)
    assert details.status_code == 200
    assert details.json()["filename"] == "mine.txt"

    assert client.get(f"/files/{file_id}", headers=other_auth_headers).status_code == 404
    assert client.delete(f"/files/{file_id}", headers=other_auth_headers).status_code == 404

    deleted = client.delete(f"/files/{file_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(link + "/download").status_code == 404

    history = client.get("/files/history", headers=auth_headers)
    assert history.status_code == 200
    assert history.json()["items"][0]["status"] == "deleted"
    assert history.json()["items"][0]["filename"] == "mine.txt"
    assert client.get("/files", headers=auth_headers).json()["total"] == 0
    assert client.get("/users/me/storage", headers=auth_headers).json()["used_bytes"] == 0


def test_expired_file_goes_to_history_and_leaves_quota(client, auth_headers):
    uploaded = _upload(client, auth_headers, name="soon.txt", content=b"expire-me", expires_in="5")
    body = uploaded.json()
    storage_file = Path(settings.storage_dir) / body["id"]
    assert storage_file.is_file()

    with SessionLocal() as db:
        db.execute(
            text("UPDATE files SET expires_at = :ts WHERE id = :id"),
            {"ts": datetime.now(timezone.utc) - timedelta(seconds=5), "id": body["id"]},
        )
        db.commit()

    landing = client.get(body["download_url"])
    assert landing.status_code == 410

    active = client.get("/files", headers=auth_headers)
    assert active.json()["total"] == 0
    assert not storage_file.exists()
    with SessionLocal() as db:
        purged_at = db.execute(
            text("SELECT purged_at FROM files WHERE id = :id"), {"id": body["id"]}
        ).scalar_one()
    assert purged_at is not None

    history = client.get("/files/history", headers=auth_headers).json()["items"]
    assert any(item["id"] == body["id"] and item["status"] == "expired" for item in history)
    assert client.get("/users/me/storage", headers=auth_headers).json()["used_bytes"] == 0


def test_unknown_token_and_rate_limit(client, auth_headers):
    assert client.get("/d/does-not-exist").status_code == 404

    uploaded = _upload(client, auth_headers, content=b"limited")
    link = uploaded.json()["download_url"] + "/download"

    settings.download_rate_limit = 2
    get_redis().delete("rate_limit:testclient")
    statuses = [client.get(link).status_code for _ in range(3)]
    assert statuses == [200, 200, 429]
