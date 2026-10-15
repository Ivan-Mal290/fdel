def test_register_login_and_me(client):
    registered = client.post(
        "/auth/register",
        json={"email": "User@Example.com", "password": "password123"},
    )
    assert registered.status_code == 201
    body = registered.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    duplicate = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "email_taken"

    short = client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )
    assert short.status_code == 422
    assert short.json()["code"] == "validation_error"

    bad_login = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["code"] == "invalid_credentials"

    login = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    me = client.get("/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"
    assert "password" not in me.text


def test_refresh_rotates_and_rejects_reuse(client):
    registered = client.post(
        "/auth/register",
        json={"email": "refresh@example.com", "password": "password123"},
    )
    old_refresh = registered.json()["refresh_token"]

    refreshed = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != old_refresh

    reused = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401
    assert reused.json()["code"] == "invalid_token"


def test_logout_revokes_refresh_token(client):
    registered = client.post(
        "/auth/register",
        json={"email": "logout@example.com", "password": "password123"},
    )
    refresh_token = registered.json()["refresh_token"]

    logged_out = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logged_out.status_code == 204

    reused = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert reused.status_code == 401
    assert reused.json()["code"] == "invalid_token"
