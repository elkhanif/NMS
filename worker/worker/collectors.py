import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.enums import (
    AddressSource,
    AlertSeverity,
    AlertStatus,
    DeviceStatus,
    EventSeverity,
    EventType,
    InterfaceStatus,
    MetricType,
)
from nms_common.models import Alert, Device, DeviceAddress, DeviceStateHistory, Event, Interface, InterfaceMetric, Metric
from nms_common.ws_events import queue_event

from worker import alert_engine


def record_metric(db: AsyncSession, device_id: uuid.UUID, metric_type: MetricType, value: float | None, unit: str | None = None) -> None:
    if value is None:
        return
    db.add(Metric(device_id=device_id, metric_type=metric_type, value=value, unit=unit))


async def update_reachability(db: AsyncSession, device: Device, reachable: bool) -> None:
    """Handles the ICMP/TCP/HTTP-derived up/down transition (device unreachable), independent
    of metric-threshold-driven WARNING/CRITICAL state (see refresh_device_status)."""
    now = datetime.now(timezone.utc)
    was_down = device.status == DeviceStatus.DOWN

    if reachable:
        device.last_seen = now
        if was_down or device.status == DeviceStatus.UNKNOWN:
            device.status = DeviceStatus.UP
        if was_down:
            db.add(
                Event(
                    device_id=device.id,
                    event_type=EventType.DEVICE_RECOVERED,
                    severity=EventSeverity.INFO,
                    message=f"{device.hostname} ({device.ip_address}) recovered",
                )
            )
            queue_event(db, "event", "created", device_id=device.id, event_type=EventType.DEVICE_RECOVERED.value)
    elif not was_down:
        device.status = DeviceStatus.DOWN
        db.add(
            Event(
                device_id=device.id,
                event_type=EventType.DEVICE_DOWN,
                severity=EventSeverity.CRITICAL,
                message=f"{device.hostname} ({device.ip_address}) is unreachable",
            )
        )
        queue_event(db, "event", "created", device_id=device.id, event_type=EventType.DEVICE_DOWN.value)

    await alert_engine.evaluate_unreachable(db, device, reachable)


async def record_state_transition(db: AsyncSession, device: Device, previous_status: DeviceStatus) -> None:
    """Writes one device_state_history row whenever this poll cycle's status update
    (update_reachability + refresh_device_status, already applied by the caller)
    actually changed device.status -- this is the numeric/interval-friendly source
    for uptime %, "last outage window", and the correlator's timestamp math, kept
    separate from the human-readable Event log. Also emits DEVICE_NEW the very
    first time a device gets a status at all (no prior history row exists)."""
    if device.status == previous_status:
        return

    prior = await db.execute(
        select(DeviceStateHistory.id).where(DeviceStateHistory.device_id == device.id).limit(1)
    )
    is_first = prior.scalar_one_or_none() is None

    if is_first:
        db.add(
            Event(
                device_id=device.id,
                event_type=EventType.DEVICE_NEW,
                severity=EventSeverity.INFO,
                message=f"{device.hostname} ({device.ip_address}) discovered and being monitored",
            )
        )
        queue_event(db, "event", "created", device_id=device.id, event_type=EventType.DEVICE_NEW.value)

    db.add(DeviceStateHistory(device_id=device.id, previous_status=previous_status, new_status=device.status))


async def record_address_observation(db: AsyncSession, device: Device, observed_mac: str | None = None) -> None:
    """Compares the currently-polled IP (always) and, when this poll cycle yielded
    one (SNMP only, from the primary interface's ifPhysAddress), the observed MAC
    against the last-known `device_addresses` row. Only ever called after a
    reachable poll -- a failed/timed-out poll carries no trustworthy identity data.

    `device_addresses` is the single source of truth for IP/MAC history;
    `device.mac_address` is kept as a denormalized cache of the current row purely
    for cheap search/display, always written from here, never independently.
    """
    result = await db.execute(
        select(DeviceAddress)
        .where(DeviceAddress.device_id == device.id, DeviceAddress.is_current.is_(True))
        .limit(1)
    )
    current = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if current is None:
        db.add(
            DeviceAddress(
                device_id=device.id,
                ip_address=device.ip_address,
                mac_address=observed_mac,
                source=AddressSource.POLL_OBSERVED,
            )
        )
        if observed_mac:
            device.mac_address = observed_mac
        return

    ip_changed = current.ip_address != device.ip_address
    mac_changed = bool(observed_mac) and current.mac_address != observed_mac

    if not ip_changed and not mac_changed:
        current.last_seen_at = now
        return

    current.is_current = False
    db.add(
        DeviceAddress(
            device_id=device.id,
            ip_address=device.ip_address,
            mac_address=observed_mac if observed_mac else current.mac_address,
            source=AddressSource.POLL_OBSERVED,
        )
    )

    if ip_changed:
        db.add(
            Event(
                device_id=device.id,
                event_type=EventType.IP_CHANGED,
                severity=EventSeverity.WARNING,
                message=f"{device.hostname} IP changed: {current.ip_address} -> {device.ip_address}",
                event_metadata={"old_ip": current.ip_address, "new_ip": device.ip_address},
            )
        )
        queue_event(db, "event", "created", device_id=device.id, event_type=EventType.IP_CHANGED.value)
    if mac_changed:
        db.add(
            Event(
                device_id=device.id,
                event_type=EventType.MAC_CHANGED,
                severity=EventSeverity.WARNING,
                message=f"{device.hostname} MAC changed: {current.mac_address or 'unknown'} -> {observed_mac}",
                event_metadata={"old_mac": current.mac_address, "new_mac": observed_mac},
            )
        )
        queue_event(db, "event", "created", device_id=device.id, event_type=EventType.MAC_CHANGED.value)
        device.mac_address = observed_mac


async def refresh_device_status(db: AsyncSession, device: Device) -> None:
    """Derives WARNING/CRITICAL from open alerts once reachability (DOWN) has already
    been handled -- DOWN always wins, otherwise status reflects the worst open alert."""
    if device.status == DeviceStatus.DOWN:
        return

    result = await db.execute(
        select(Alert.severity, func.count())
        .where(Alert.device_id == device.id, Alert.status != AlertStatus.RESOLVED)
        .group_by(Alert.severity)
    )
    counts = dict(result.all())
    if counts.get(AlertSeverity.CRITICAL):
        device.status = DeviceStatus.CRITICAL
    elif counts.get(AlertSeverity.WARNING):
        device.status = DeviceStatus.WARNING
    else:
        device.status = DeviceStatus.UP


async def sync_interfaces(db: AsyncSession, device: Device, snmp_interfaces: list[dict]) -> None:
    if not snmp_interfaces:
        return

    existing_result = await db.execute(select(Interface).where(Interface.device_id == device.id))
    existing = {i.if_index: i for i in existing_result.scalars().all()}

    now = datetime.now(timezone.utc)

    for raw in snmp_interfaces:
        if_index = raw.get("if_index")
        if if_index is None:
            continue

        oper_status = InterfaceStatus[raw["oper_status"]] if raw.get("oper_status") else InterfaceStatus.UNKNOWN
        admin_status = InterfaceStatus[raw["admin_status"]] if raw.get("admin_status") else InterfaceStatus.UNKNOWN

        iface = existing.get(if_index)
        was_up = iface.oper_status == InterfaceStatus.UP if iface else None

        if iface is None:
            iface = Interface(
                device_id=device.id,
                if_index=if_index,
                name=raw.get("name") or f"if{if_index}",
                alias=raw.get("alias"),
                oper_status=oper_status,
                admin_status=admin_status,
                speed_bps=raw.get("speed_bps"),
                mac_address=raw.get("mac_address"),
            )
            db.add(iface)
            await db.flush()
            existing[if_index] = iface
        else:
            iface.name = raw.get("name") or iface.name
            iface.alias = raw.get("alias")
            iface.speed_bps = raw.get("speed_bps") or iface.speed_bps
            iface.mac_address = raw.get("mac_address") or iface.mac_address
            if iface.oper_status != oper_status:
                iface.last_change_at = now
            iface.oper_status = oper_status
            iface.admin_status = admin_status
            iface.updated_at = now

        now_up = oper_status == InterfaceStatus.UP
        if was_up is not None and was_up != now_up:
            event_type = EventType.INTERFACE_RECOVERED if now_up else EventType.INTERFACE_DOWN
            db.add(
                Event(
                    device_id=device.id,
                    interface_id=iface.id,
                    event_type=event_type,
                    severity=EventSeverity.INFO if now_up else EventSeverity.WARNING,
                    message=f"Interface {iface.name} on {device.hostname} is {'up' if now_up else 'down'}",
                )
            )
            queue_event(db, "event", "created", device_id=device.id, event_type=event_type.value)
        if was_up is not None:
            await alert_engine.evaluate_interface_down(db, device, iface.id, iface.name, is_down=not now_up)

        in_octets = raw.get("in_octets")
        out_octets = raw.get("out_octets")
        in_bps = out_bps = None
        if in_octets is not None or out_octets is not None:
            prev_result = await db.execute(
                select(InterfaceMetric)
                .where(InterfaceMetric.interface_id == iface.id)
                .order_by(InterfaceMetric.time.desc())
                .limit(1)
            )
            prev = prev_result.scalar_one_or_none()
            if prev is not None:
                elapsed = (now - prev.time).total_seconds()
                if elapsed > 0:
                    if in_octets is not None and prev.in_octets is not None and in_octets >= prev.in_octets:
                        in_bps = (in_octets - prev.in_octets) * 8 / elapsed
                    if out_octets is not None and prev.out_octets is not None and out_octets >= prev.out_octets:
                        out_bps = (out_octets - prev.out_octets) * 8 / elapsed

            db.add(
                InterfaceMetric(
                    interface_id=iface.id,
                    in_octets=in_octets,
                    out_octets=out_octets,
                    in_bps=in_bps,
                    out_bps=out_bps,
                    errors_in=raw.get("errors_in"),
                    errors_out=raw.get("errors_out"),
                    discards_in=raw.get("discards_in"),
                    discards_out=raw.get("discards_out"),
                )
            )
