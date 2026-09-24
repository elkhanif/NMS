from nms_common.crypto import hash_password
from nms_common.enums import UserRole
from nms_common.models import User


async def _login(client, email, password):
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_viewer_cannot_create_device(client, db_session):
    viewer = User(email="viewer@test.com", hashed_password=hash_password("viewerpass123"), role=UserRole.VIEWER)
    db_session.add(viewer)
    await db_session.commit()
    token = await _login(client, "viewer@test.com", "viewerpass123")

    resp = await client.post(
        "/api/v1/devices/",
        json={"hostname": "sw1", "ip_address": "10.10.0.5", "device_type": "SWITCH"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_viewer_can_read_devices(client, db_session):
    viewer = User(email="viewer2@test.com", hashed_password=hash_password("viewerpass123"), role=UserRole.VIEWER)
    db_session.add(viewer)
    await db_session.commit()
    token = await _login(client, "viewer2@test.com", "viewerpass123")

    resp = await client.get("/api/v1/devices/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


async def test_admin_can_create_device(client, admin_token):
    resp = await client.post(
        "/api/v1/devices/",
        json={"hostname": "sw1", "ip_address": "10.10.0.6", "device_type": "SWITCH"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["hostname"] == "sw1"


async def test_non_admin_cannot_manage_users(client, db_session):
    engineer = User(
        email="engineer@test.com",
        hashed_password=hash_password("engineerpass123"),
        role=UserRole.NETWORK_ENGINEER,
    )
    db_session.add(engineer)
    await db_session.commit()
    token = await _login(client, "engineer@test.com", "engineerpass123")

    resp = await client.get("/api/v1/users/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
