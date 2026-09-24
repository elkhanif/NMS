from nms_common.crypto import hash_password
from nms_common.enums import UserRole
from nms_common.models import User


async def test_login_requires_valid_password(client, admin_user):
    resp = await client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "wrong"})
    assert resp.status_code == 401


async def test_admin_can_create_and_fetch_device(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    created = await client.post(
        "/api/v1/devices/",
        json={"hostname": "test-router", "ip_address": "10.10.0.1", "device_type": "ROUTER"},
        headers=headers,
    )
    assert created.status_code == 201
    device_id = created.json()["id"]

    fetched = await client.get(f"/api/v1/devices/{device_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["ip_address"] == "10.10.0.1"
    assert fetched.json()["checks"] == []


async def test_viewer_cannot_create_device(client, db_session):
    viewer = User(
        email="viewer@test.com", hashed_password=hash_password("viewerpass123"), role=UserRole.VIEWER, is_active=True
    )
    db_session.add(viewer)
    await db_session.commit()

    login = await client.post(
        "/api/v1/auth/login", json={"email": "viewer@test.com", "password": "viewerpass123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.post(
        "/api/v1/devices/", json={"hostname": "x", "ip_address": "10.10.0.2"}, headers=headers
    )
    assert resp.status_code == 403


async def test_credentials_are_never_returned_in_plaintext(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    device = (
        await client.post(
            "/api/v1/devices/",
            json={"hostname": "snmp-router", "ip_address": "10.10.0.3", "device_type": "ROUTER"},
            headers=headers,
        )
    ).json()

    resp = await client.post(
        f"/api/v1/devices/{device['id']}/credentials",
        json={"credential_type": "SNMPV2C", "payload": {"community": "super-secret"}},
        headers=headers,
    )
    assert resp.status_code == 201
    assert "payload" not in resp.json()
    assert "encrypted_payload" not in resp.json()
    assert "super-secret" not in resp.text
