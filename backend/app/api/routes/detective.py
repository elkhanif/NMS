import ipaddress
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.enums import DeviceStatus, EventType, MetricType
from nms_common.models import (
    Device,
    DeviceAddress,
    DeviceRelationship,
    DeviceStateHistory,
    Event,
    Interface,
    Metric,
)

from app.deps import get_current_user, get_db
from app.schemas.detective import (
    DetectiveMatch,
    DetectiveSearchResult,
    DeviceIdentity,
    DeviceInvestigation,
    HealthSnapshot,
    InvestigationSummary,
    NetworkIdentity,
    RelationshipNode,
    TimelineEntry,
)
from app.schemas.device import InterfaceOut

router = APIRouter(prefix="/detective", tags=["detective"], dependencies=[Depends(get_current_user)])


@router.get("/search", response_model=DetectiveSearchResult)
async def search(q: str = Query(min_length=1), db: AsyncSession = Depends(get_db)) -> DetectiveSearchResult:
    """User can search by IP, MAC, hostname, device ID, or serial number -- including
    historical IP/MAC (device_addresses), so a device found by an IP it used to have
    still resolves.

    IP and MAC matches are exact-only: on a real inventory of a few hundred devices
    sharing a subnet (e.g. every "192.168.0.x" device), a substring ILIKE on IP turns
    "192.168.0.1" into a noisy match against .10, .11, .100...199 etc. Hostname
    matching stays substring/fuzzy (ILIKE), since partial hostnames like "KHANIF" are
    genuinely useful for finding "KHANIF-PC".
    """
    matches: list[DetectiveMatch] = []
    seen: set[uuid.UUID] = set()

    def add(device: Device, match_type: str, matched_value: str) -> None:
        if device.id in seen:
            return
        seen.add(device.id)
        matches.append(
            DetectiveMatch(
                device_id=device.id,
                hostname=device.hostname,
                ip_address=device.ip_address,
                match_type=match_type,
                matched_value=matched_value,
            )
        )

    ql = q.strip().lower()

    try:
        device_id = uuid.UUID(q)
    except ValueError:
        device_id = None
    if device_id is not None:
        device = await db.get(Device, device_id)
        if device is not None:
            add(device, "device_id", str(device.id))

    is_ip = False
    try:
        ipaddress.ip_address(q.strip())
        is_ip = True
    except ValueError:
        pass

    exact_result = await db.execute(
        select(Device).where(
            or_(
                func.lower(Device.ip_address) == ql,
                func.lower(Device.hostname) == ql,
                func.lower(Device.mac_address) == ql,
                func.lower(Device.serial_number) == ql,
            )
        )
    )
    for device in exact_result.scalars().all():
        if device.ip_address and device.ip_address.lower() == ql:
            add(device, "ip", device.ip_address)
        elif device.hostname and device.hostname.lower() == ql:
            add(device, "hostname", device.hostname)
        elif device.mac_address and device.mac_address.lower() == ql:
            add(device, "mac", device.mac_address)
        elif device.serial_number and device.serial_number.lower() == ql:
            add(device, "serial_number", device.serial_number)

    if not is_ip and len(q) >= 2:
        hostname_result = await db.execute(select(Device).where(Device.hostname.ilike(f"%{q}%")).limit(20))
        for device in hostname_result.scalars().all():
            add(device, "hostname", device.hostname)

    exact_hist_result = await db.execute(
        select(DeviceAddress).where(
            or_(func.lower(DeviceAddress.ip_address) == ql, func.lower(DeviceAddress.mac_address) == ql)
        )
    )
    for addr in exact_hist_result.scalars().all():
        device = await db.get(Device, addr.device_id)
        if device is None:
            continue
        if addr.ip_address and addr.ip_address.lower() == ql:
            add(device, "ip_history", addr.ip_address)
        elif addr.mac_address and addr.mac_address.lower() == ql:
            add(device, "mac_history", addr.mac_address)

    return DetectiveSearchResult(query=q, matches=matches[:20])


async def _latest_metric(db: AsyncSession, device_id: uuid.UUID, metric_type: MetricType) -> float | None:
    result = await db.execute(
        select(Metric.value)
        .where(Metric.device_id == device_id, Metric.metric_type == metric_type)
        .order_by(Metric.time.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _avg_metric_24h(db: AsyncSession, device_id: uuid.UUID, metric_type: MetricType, since: datetime) -> float | None:
    result = await db.execute(
        select(func.avg(Metric.value)).where(
            Metric.device_id == device_id, Metric.metric_type == metric_type, Metric.time >= since
        )
    )
    return result.scalar_one_or_none()


@router.get("/{device_id}", response_model=DeviceInvestigation)
async def investigate(device_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> DeviceInvestigation:
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    first_seen_result = await db.execute(
        select(DeviceStateHistory.changed_at)
        .where(DeviceStateHistory.device_id == device_id)
        .order_by(DeviceStateHistory.changed_at)
        .limit(1)
    )
    first_seen = first_seen_result.scalar_one_or_none() or device.created_at

    identity = DeviceIdentity(
        hostname=device.hostname,
        ip_address=device.ip_address,
        mac_address=device.mac_address,
        vendor=device.vendor,
        model=device.model,
        device_type=device.device_type,
        status=device.status,
        first_seen=first_seen,
        last_seen=device.last_seen,
        serial_number=device.serial_number,
    )

    parent_result = await db.execute(select(DeviceRelationship).where(DeviceRelationship.child_device_id == device_id))
    parent_edge = parent_result.scalars().first()
    switch_hostname = switch_port = None
    parent_device_id = None
    if parent_edge is not None:
        parent_device_id = parent_edge.parent_device_id
        parent_device = await db.get(Device, parent_edge.parent_device_id)
        switch_hostname = parent_device.hostname if parent_device else None
        if parent_edge.child_interface_id:
            iface = await db.get(Interface, parent_edge.child_interface_id)
            switch_port = iface.name if iface else None

    children_result = await db.execute(select(DeviceRelationship).where(DeviceRelationship.parent_device_id == device_id))
    child_edges = list(children_result.scalars().all())

    network_identity = NetworkIdentity(
        gateway=device.default_gateway_ip,
        vlan=None,
        subnet=None,
        switch_hostname=switch_hostname,
        switch_port=switch_port,
        access_point=None,
        parent_device_id=parent_device_id,
        connected_device_ids=[e.child_device_id for e in child_edges],
    )

    ifaces_result = await db.execute(select(Interface).where(Interface.device_id == device_id).order_by(Interface.if_index))
    interfaces = list(ifaces_result.scalars().all())

    health = HealthSnapshot(
        availability_pct=await _latest_metric(db, device_id, MetricType.AVAILABILITY),
        latency_ms=await _latest_metric(db, device_id, MetricType.RESPONSE_TIME),
        packet_loss_pct=await _latest_metric(db, device_id, MetricType.PACKET_LOSS),
        cpu_percent=await _latest_metric(db, device_id, MetricType.CPU_USAGE),
        memory_percent=await _latest_metric(db, device_id, MetricType.MEMORY_USAGE),
        interfaces=[InterfaceOut.model_validate(i) for i in interfaces],
        traffic_in_bps=None,
        traffic_out_bps=None,
    )

    events_result = await db.execute(
        select(Event).where(Event.device_id == device_id).order_by(Event.created_at.desc()).limit(100)
    )
    timeline = [
        TimelineEntry(time=e.created_at, event_type=e.event_type.value, message=e.message, severity=e.severity.value)
        for e in events_result.scalars().all()
    ]

    ancestors: list[RelationshipNode] = []
    current_id = device_id
    for _ in range(10):  # depth cap in case of a topology cycle
        edge_result = await db.execute(select(DeviceRelationship).where(DeviceRelationship.child_device_id == current_id))
        edge = edge_result.scalars().first()
        if edge is None:
            break
        parent = await db.get(Device, edge.parent_device_id)
        if parent is None:
            break
        iface = await db.get(Interface, edge.child_interface_id) if edge.child_interface_id else None
        ancestors.append(
            RelationshipNode(
                device_id=parent.id,
                hostname=parent.hostname,
                status=parent.status,
                relationship_type=edge.relationship_type,
                interface_name=iface.name if iface else None,
            )
        )
        current_id = parent.id

    children: list[RelationshipNode] = []
    for edge in child_edges:
        child = await db.get(Device, edge.child_device_id)
        if child is None:
            continue
        iface = await db.get(Interface, edge.child_interface_id) if edge.child_interface_id else None
        children.append(
            RelationshipNode(
                device_id=child.id,
                hostname=child.hostname,
                status=child.status,
                relationship_type=edge.relationship_type,
                interface_name=iface.name if iface else None,
            )
        )

    last_down_result = await db.execute(
        select(DeviceStateHistory)
        .where(DeviceStateHistory.device_id == device_id, DeviceStateHistory.new_status == DeviceStatus.DOWN)
        .order_by(DeviceStateHistory.changed_at.desc())
        .limit(1)
    )
    last_down = last_down_result.scalar_one_or_none()
    last_outage_start = last_down.changed_at if last_down else None
    last_outage_end = None
    if last_down is not None:
        recovery_result = await db.execute(
            select(DeviceStateHistory)
            .where(
                DeviceStateHistory.device_id == device_id,
                DeviceStateHistory.changed_at > last_down.changed_at,
                DeviceStateHistory.new_status != DeviceStatus.DOWN,
            )
            .order_by(DeviceStateHistory.changed_at)
            .limit(1)
        )
        recovery = recovery_result.scalar_one_or_none()
        last_outage_end = recovery.changed_at if recovery else None

    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)

    ip_changes_result = await db.execute(
        select(func.count())
        .select_from(Event)
        .where(Event.device_id == device_id, Event.event_type == EventType.IP_CHANGED, Event.created_at >= day_ago)
    )
    mac_changes_result = await db.execute(
        select(func.count())
        .select_from(Event)
        .where(Event.device_id == device_id, Event.event_type == EventType.MAC_CHANGED, Event.created_at >= day_ago)
    )

    connected_through = None
    if switch_hostname and switch_port:
        connected_through = f"{switch_hostname} / {switch_port}"
    elif switch_hostname:
        connected_through = switch_hostname

    summary = InvestigationSummary(
        current_status=device.status,
        last_outage_start=last_outage_start,
        last_outage_end=last_outage_end,
        avg_latency_ms=await _avg_metric_24h(db, device_id, MetricType.RESPONSE_TIME, day_ago),
        packet_loss_pct=await _avg_metric_24h(db, device_id, MetricType.PACKET_LOSS, day_ago),
        ip_changes_24h=ip_changes_result.scalar_one() or 0,
        mac_changes_24h=mac_changes_result.scalar_one() or 0,
        connected_through=connected_through,
    )

    return DeviceInvestigation(
        identity=identity,
        network_identity=network_identity,
        health=health,
        timeline=timeline,
        ancestors=ancestors,
        children=children,
        summary=summary,
    )
