from sqlalchemy import select

from nms_common.enums import DeviceStatus, DeviceType, EventType, InterfaceStatus
from nms_common.models import Device, Event, Interface

from worker import collectors


async def test_device_down_then_recovered_emits_events(db_session):
    device = Device(
        hostname="ap1", ip_address="10.10.0.20", device_type=DeviceType.ACCESS_POINT, status=DeviceStatus.UP
    )
    db_session.add(device)
    await db_session.flush()

    await collectors.update_reachability(db_session, device, reachable=False)
    assert device.status == DeviceStatus.DOWN

    await collectors.update_reachability(db_session, device, reachable=True)
    assert device.status == DeviceStatus.UP

    result = await db_session.execute(select(Event).where(Event.device_id == device.id).order_by(Event.created_at))
    event_types = [e.event_type for e in result.scalars().all()]
    assert EventType.DEVICE_DOWN in event_types
    assert EventType.DEVICE_RECOVERED in event_types


async def test_sync_interfaces_creates_and_detects_transition(db_session):
    device = Device(hostname="sw1", ip_address="10.10.0.21", device_type=DeviceType.SWITCH)
    db_session.add(device)
    await db_session.flush()

    await collectors.sync_interfaces(
        db_session,
        device,
        [{"if_index": 1, "name": "Gi0/1", "oper_status": "UP", "admin_status": "UP", "speed_bps": 1_000_000_000}],
    )
    result = await db_session.execute(select(Interface).where(Interface.device_id == device.id))
    iface = result.scalar_one()
    assert iface.oper_status == InterfaceStatus.UP

    await collectors.sync_interfaces(
        db_session,
        device,
        [{"if_index": 1, "name": "Gi0/1", "oper_status": "DOWN", "admin_status": "UP", "speed_bps": 1_000_000_000}],
    )
    await db_session.refresh(iface)
    assert iface.oper_status == InterfaceStatus.DOWN

    result = await db_session.execute(
        select(Event).where(Event.interface_id == iface.id, Event.event_type == EventType.INTERFACE_DOWN)
    )
    assert result.scalar_one_or_none() is not None
