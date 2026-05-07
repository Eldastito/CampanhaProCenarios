"""Tests for /auth/register, /auth/login, /auth/me endpoints."""



# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


def test_register_creates_user_and_returns_token(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "password": "strongpass1",
            "organization_id": "org_demo_001",
            "role": "analyst",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20
    assert body["email"] == "new@example.com"
    assert body["organization_id"] == "org_demo_001"
    assert body["role"] == "analyst"


def test_register_returns_409_on_duplicate_email(client):
    payload = {
        "email": "dup@example.com",
        "password": "strongpass1",
        "organization_id": "org_demo_001",
    }
    client.post("/api/v1/auth/register", json=payload)
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


def test_register_returns_404_for_unknown_org(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "orphan@example.com",
            "password": "strongpass1",
            "organization_id": "org_does_not_exist",
        },
    )
    assert resp.status_code == 404


def test_register_rejects_short_password(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "short@example.com",
            "password": "abc",
            "organization_id": "org_demo_001",
        },
    )
    assert resp.status_code == 422


def test_register_rejects_invalid_role(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "badrole@example.com",
            "password": "strongpass1",
            "organization_id": "org_demo_001",
            "role": "superuser",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_returns_token_for_valid_credentials(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "mypassword1",
            "organization_id": "org_demo_001",
        },
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "mypassword1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


def test_login_returns_401_for_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrong@example.com",
            "password": "correctpass",
            "organization_id": "org_demo_001",
        },
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 401


def test_login_returns_401_for_unknown_email(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "anything"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------


def test_me_returns_user_profile_for_valid_token(client, analyst_auth_headers):
    resp = client.get("/api/v1/auth/me", headers=analyst_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "analyst@test.example"
    assert body["organization_id"] == "org_demo_001"
    assert body["role"] == "analyst"
    assert body["is_active"] is True
    assert "created_at" in body


def test_me_returns_401_without_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_401_with_invalid_token(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401
