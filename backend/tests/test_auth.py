async def test_login_success(client, admin_user):
    resp = await client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "adminpass123"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_login_wrong_password(client, admin_user):
    resp = await client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "wrong"})
    assert resp.status_code == 401


async def test_me_requires_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_with_token(client, admin_token):
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@test.com"


async def test_refresh_issues_new_tokens(client, admin_user):
    login = await client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "adminpass123"})
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
