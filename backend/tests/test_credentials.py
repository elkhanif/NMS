from sqlalchemy import select

from nms_common.models import DeviceCredential

from app.services.credentials import decrypt_credential


async def test_credential_roundtrip_and_never_exposed(client, admin_token, db_session):
    dev_resp = await client.post(
        "/api/v1/devices/",
        json={"hostname": "router1", "ip_address": "10.10.0.1", "device_type": "ROUTER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert dev_resp.status_code == 201
    device_id = dev_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/devices/{device_id}/credentials",
        json={"credential_type": "SNMPV2C", "payload": {"community": "supersecret"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "payload" not in body
    assert "encrypted_payload" not in body
    assert "supersecret" not in str(body)

    list_resp = await client.get(
        f"/api/v1/devices/{device_id}/credentials", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert "supersecret" not in list_resp.text

    result = await db_session.execute(select(DeviceCredential).where(DeviceCredential.device_id == device_id))
    credential = result.scalar_one()
    assert credential.encrypted_payload != b"supersecret"
    assert decrypt_credential(credential) == {"community": "supersecret"}
