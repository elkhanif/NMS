import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nms_common.enums import CredentialType, DeviceStatus, DeviceType, EventSeverity, EventType, MetricType
from nms_common.models import Alert, Device, DeviceAddress, DeviceCheck, DeviceCredential, Event, Interface, Metric, User

from app.deps import get_current_user, get_db, require_config_writer
from app.schemas.alert import AlertOut
from app.schemas.device import (
    BulkCheckIn,
    BulkCredentialIn,
    DeviceAddressOut,
    DeviceCheckIn,
    DeviceCheckOut,
    DeviceCreate,
    DeviceCredentialIn,
    DeviceCredentialOut,
    DeviceDetailOut,
    DeviceOut,
    DeviceUpdate,
    InterfaceOut,
    LatestMetricOut,
)
from app.schemas.event import EventOut
from app.schemas.metric import MetricPoint, MetricSeries
from app.services.audit import write_audit
from app.services.credentials import upsert_credential

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/", response_model=list[DeviceOut], dependencies=[Depends(get_current_user)])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    location_id: uuid.UUID | None = None,
    device_type: DeviceType | None = None,
    vendor: str | None = None,
    status_filter: DeviceStatus | None = Query(default=None, alias="status"),
    search: str | None = None,
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
) -> list[Device]:
    stmt = select(Device)
    if location_id:
        stmt = stmt.where(Device.location_id == location_id)
    if device_type:
        stmt = stmt.where(Device.device_type == device_type)
    if vendor:
        stmt = stmt.where(Device.vendor == vendor)
    if status_filter:
        stmt = stmt.where(Device.status == status_filter)
    if search:
        like = f"%{search}%"
        stmt = stmt.where((Device.hostname.ilike(like)) | (Device.ip_address.ilike(like)))
    stmt = stmt.order_by(Device.hostname).limit(limit).offset(offset).options(selectinload(Device.credentials))

    result = await db.execute(stmt)
    devices = list(result.scalars().all())
    snmp_types = {CredentialType.SNMPV2C, CredentialType.SNMPV3}
    for device in devices:
        device.has_snmp_credential = any(c.credential_type in snmp_types for c in device.credentials)
    return devices


@router.post("/", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def create_device(
    payload: DeviceCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_config_writer)
) -> Device:
    existing = await db.execute(select(Device).where(Device.ip_address == payload.ip_address))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A device with this IP already exists")

    device = Device(**payload.model_dump())
    db.add(device)
    await db.flush()
    await write_audit(db, current_user, "device.create", "device", device.id, {"hostname": device.hostname})
    await db.commit()
    return device


@router.post("/bulk-credentials", status_code=status.HTTP_200_OK)
async def bulk_set_credentials(
    payload: BulkCredentialIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> dict:
    """Applies one credential to many devices at once (e.g. the same SNMPv2c
    community string across a batch of freshly-imported devices) instead of
    requiring a separate visit to each device's page."""
    result = await db.execute(select(Device.id).where(Device.id.in_(payload.device_ids)))
    existing_ids = set(result.scalars().all())

    for device_id in existing_ids:
        await upsert_credential(db, device_id, payload.credential_type, payload.payload)

    await write_audit(
        db,
        current_user,
        "device.credential.bulk_set",
        "device",
        None,
        {"credential_type": payload.credential_type, "device_count": len(existing_ids)},
    )
    await db.commit()
    return {"applied_count": len(existing_ids), "skipped_ids": [str(d) for d in payload.device_ids if d not in existing_ids]}


@router.post("/bulk-checks", status_code=status.HTTP_200_OK)
async def bulk_set_checks(
    payload: BulkCheckIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> dict:
    """Applies one monitoring check (type, interval, timeout, retries, config) to
    many devices at once -- same upsert-by-(device_id, check_type) semantics as the
    single-device PUT /{device_id}/checks, just looped over a batch."""
    result = await db.execute(select(Device.id).where(Device.id.in_(payload.device_ids)))
    existing_ids = set(result.scalars().all())

    check_data = {
        "check_type": payload.check_type,
        "enabled": payload.enabled,
        "config": payload.config,
        "interval_seconds": payload.interval_seconds,
        "timeout_seconds": payload.timeout_seconds,
        "retries": payload.retries,
    }

    for device_id in existing_ids:
        existing_check_result = await db.execute(
            select(DeviceCheck).where(DeviceCheck.device_id == device_id, DeviceCheck.check_type == payload.check_type)
        )
        check = existing_check_result.scalar_one_or_none()
        if check is None:
            db.add(DeviceCheck(device_id=device_id, **check_data))
        else:
            for field, value in check_data.items():
                setattr(check, field, value)

    await write_audit(
        db,
        current_user,
        "device.check.bulk_upsert",
        "device",
        None,
        {"check_type": payload.check_type, "device_count": len(existing_ids)},
    )
    await db.commit()
    return {"applied_count": len(existing_ids), "skipped_ids": [str(d) for d in payload.device_ids if d not in existing_ids]}


@router.get("/{device_id}", response_model=DeviceDetailOut)
async def get_device(
    device_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)
) -> DeviceDetailOut:
    result = await db.execute(
        select(Device)
        .where(Device.id == device_id)
        .options(selectinload(Device.checks), selectinload(Device.interfaces))
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    latest_result = await db.execute(
        select(Metric)
        .distinct(Metric.metric_type)
        .where(Metric.device_id == device_id)
        .order_by(Metric.metric_type, Metric.time.desc())
    )
    latest_metrics = [
        LatestMetricOut(metric_type=m.metric_type.value, value=m.value, unit=m.unit, time=m.time)
        for m in latest_result.scalars().all()
    ]

    return DeviceDetailOut(
        **DeviceOut.model_validate(device).model_dump(),
        checks=[DeviceCheckOut.model_validate(c) for c in device.checks],
        interfaces=[i for i in device.interfaces],
        latest_metrics=latest_metrics,
    )


@router.patch("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: uuid.UUID,
    payload: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> Device:
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    data = payload.model_dump(exclude_unset=True)

    if "default_gateway_ip" in data and data["default_gateway_ip"] != device.default_gateway_ip:
        db.add(
            Event(
                device_id=device.id,
                event_type=EventType.GATEWAY_CHANGED,
                severity=EventSeverity.INFO,
                message=f"{device.hostname} default gateway changed: "
                f"{device.default_gateway_ip or 'Unknown'} -> {data['default_gateway_ip'] or 'Unknown'}",
                event_metadata={"old_gateway": device.default_gateway_ip, "new_gateway": data["default_gateway_ip"]},
            )
        )

    for field, value in data.items():
        setattr(device, field, value)
    await write_audit(db, current_user, "device.update", "device", device_id, data)
    await db.commit()
    await db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> None:
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    await db.delete(device)
    await write_audit(db, current_user, "device.delete", "device", device_id)
    await db.commit()


@router.put("/{device_id}/checks", response_model=DeviceCheckOut)
async def upsert_check(
    device_id: uuid.UUID,
    payload: DeviceCheckIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> DeviceCheck:
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    result = await db.execute(
        select(DeviceCheck).where(DeviceCheck.device_id == device_id, DeviceCheck.check_type == payload.check_type)
    )
    check = result.scalar_one_or_none()
    data = payload.model_dump()
    if check is None:
        check = DeviceCheck(device_id=device_id, **data)
        db.add(check)
    else:
        for field, value in data.items():
            setattr(check, field, value)

    await write_audit(db, current_user, "device.check.upsert", "device", device_id, data)
    await db.commit()
    await db.refresh(check)
    return check


@router.get("/{device_id}/addresses", response_model=list[DeviceAddressOut])
async def get_device_addresses(
    device_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[DeviceAddress]:
    """IP/MAC history for a device -- backs Network Detective's "IP changes: N
    times" summary and IP/MAC history search results."""
    result = await db.execute(
        select(DeviceAddress).where(DeviceAddress.device_id == device_id).order_by(DeviceAddress.first_seen_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{device_id}/credentials", response_model=DeviceCredentialOut, status_code=status.HTTP_201_CREATED)
async def set_credential(
    device_id: uuid.UUID,
    payload: DeviceCredentialIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> DeviceCredential:
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    credential = await upsert_credential(db, device_id, payload.credential_type, payload.payload)
    await write_audit(
        db, current_user, "device.credential.set", "device", device_id, {"credential_type": payload.credential_type}
    )
    await db.commit()
    await db.refresh(credential)
    return credential


@router.get("/{device_id}/credentials", response_model=list[DeviceCredentialOut])
async def list_credentials(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_config_writer),
) -> list[DeviceCredential]:
    result = await db.execute(select(DeviceCredential).where(DeviceCredential.device_id == device_id))
    return list(result.scalars().all())


@router.get("/{device_id}/interfaces", response_model=list[InterfaceOut])
async def get_device_interfaces(
    device_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[Interface]:
    result = await db.execute(select(Interface).where(Interface.device_id == device_id).order_by(Interface.if_index))
    return list(result.scalars().all())


@router.get("/{device_id}/metrics", response_model=MetricSeries)
async def get_device_metrics(
    device_id: uuid.UUID,
    metric_type: MetricType,
    hours: int = Query(default=24, le=24 * 30),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> MetricSeries:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(Metric)
        .where(Metric.device_id == device_id, Metric.metric_type == metric_type, Metric.time >= since)
        .order_by(Metric.time)
    )
    rows = list(result.scalars().all())
    return MetricSeries(
        metric_type=metric_type,
        unit=rows[0].unit if rows else None,
        points=[MetricPoint(time=r.time, value=r.value) for r in rows],
    )


@router.get("/{device_id}/events", response_model=list[EventOut])
async def get_device_events(
    device_id: uuid.UUID,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Event]:
    result = await db.execute(
        select(Event).where(Event.device_id == device_id).order_by(Event.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{device_id}/alerts", response_model=list[AlertOut])
async def get_device_alerts(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Alert]:
    result = await db.execute(
        select(Alert).where(Alert.device_id == device_id).order_by(Alert.opened_at.desc())
    )
    return list(result.scalars().all())
