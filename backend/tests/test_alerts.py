from datetime import datetime, timezone

from nms_common.enums import AlertSeverity, AlertStatus
from nms_common.models import Alert


async def test_alert_ack_then_resolve_lifecycle(client, admin_token, db_session):
    dev_resp = await client.post(
        "/api/v1/devices/",
        json={"hostname": "fw1", "ip_address": "10.10.0.2", "device_type": "FIREWALL"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    device_id = dev_resp.json()["id"]

    alert = Alert(
        device_id=device_id,
        severity=AlertSeverity.CRITICAL,
        metric="AVAILABILITY",
        message="fw1 is unreachable",
        status=AlertStatus.OPEN,
        opened_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)

    ack_resp = await client.patch(
        f"/api/v1/alerts/{alert.id}/acknowledge", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ACKNOWLEDGED"
    assert ack_resp.json()["acknowledged_by_id"] is not None

    double_ack = await client.patch(
        f"/api/v1/alerts/{alert.id}/acknowledge", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert double_ack.status_code == 409

    resolve_resp = await client.patch(
        f"/api/v1/alerts/{alert.id}/resolve", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "RESOLVED"

    double_resolve = await client.patch(
        f"/api/v1/alerts/{alert.id}/resolve", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert double_resolve.status_code == 409
