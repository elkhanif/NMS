import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.enums import DiscoveryJobStatus, EventSeverity, EventType
from nms_common.models import Device, DiscoveryJob, DiscoveryResult, Event, User

from app.deps import get_current_user, get_db, require_config_writer
from app.schemas.device import DeviceCreate
from app.schemas.discovery import (
    DiscoveryImportRequest,
    DiscoveryJobOut,
    DiscoveryResultOut,
    DiscoveryStartRequest,
)
from app.services.audit import write_audit

router = APIRouter(prefix="/discovery", tags=["discovery"])

DISCOVERY_COOLDOWN_SECONDS = 30


@router.post("/", response_model=DiscoveryJobOut, status_code=status.HTTP_201_CREATED)
async def start_discovery(
    payload: DiscoveryStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> DiscoveryJob:
    recent = await db.execute(
        select(DiscoveryJob)
        .where(DiscoveryJob.status.in_([DiscoveryJobStatus.PENDING, DiscoveryJobStatus.RUNNING]))
        .order_by(DiscoveryJob.created_at.desc())
        .limit(1)
    )
    if recent.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="A discovery job is already running. Wait for it to finish before starting another.",
        )

    last = await db.execute(select(DiscoveryJob).order_by(DiscoveryJob.created_at.desc()).limit(1))
    last_job = last.scalar_one_or_none()
    if last_job and last_job.created_at > datetime.now(timezone.utc) - timedelta(seconds=DISCOVERY_COOLDOWN_SECONDS):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {DISCOVERY_COOLDOWN_SECONDS}s between discovery jobs.",
        )

    job = DiscoveryJob(
        cidr=payload.cidr,
        requested_by_id=current_user.id,
        rate_limit_pps=payload.rate_limit_pps,
        credential_ref_id=payload.credential_ref_id,
        status=DiscoveryJobStatus.PENDING,
    )
    db.add(job)
    await db.flush()
    await write_audit(db, current_user, "discovery.start", "discovery_job", job.id, {"cidr": payload.cidr})
    await db.commit()
    return job


@router.get("/", response_model=list[DiscoveryJobOut], dependencies=[Depends(get_current_user)])
async def list_discovery_jobs(db: AsyncSession = Depends(get_db), limit: int = 50) -> list[DiscoveryJob]:
    result = await db.execute(select(DiscoveryJob).order_by(DiscoveryJob.created_at.desc()).limit(limit))
    return list(result.scalars().all())


@router.get("/{job_id}", response_model=DiscoveryJobOut, dependencies=[Depends(get_current_user)])
async def get_discovery_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> DiscoveryJob:
    job = await db.get(DiscoveryJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery job not found")
    return job


@router.get("/{job_id}/results", response_model=list[DiscoveryResultOut], dependencies=[Depends(get_current_user)])
async def get_discovery_results(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[DiscoveryResult]:
    result = await db.execute(
        select(DiscoveryResult).where(DiscoveryResult.discovery_job_id == job_id).order_by(DiscoveryResult.ip_address)
    )
    return list(result.scalars().all())


@router.post("/{job_id}/import", response_model=list[DiscoveryResultOut])
async def import_discovery_results(
    job_id: uuid.UUID,
    payload: DiscoveryImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> list[DiscoveryResult]:
    result = await db.execute(
        select(DiscoveryResult).where(
            DiscoveryResult.discovery_job_id == job_id, DiscoveryResult.id.in_(payload.result_ids)
        )
    )
    results = list(result.scalars().all())
    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching discovery results")

    overrides_by_result = {o.result_id: o for o in payload.overrides}

    imported = []
    for r in results:
        if r.imported:
            continue
        existing = await db.execute(select(Device).where(Device.ip_address == r.ip_address))
        if existing.scalar_one_or_none() is not None:
            continue

        override = overrides_by_result.get(r.id)
        device = Device(
            hostname=(override.hostname if override else None) or r.hostname_guess or r.ip_address,
            ip_address=r.ip_address,
            mac_address=r.mac_address,
            device_type=(override.device_type if override else None)
            or r.suggested_device_type
            or DeviceCreate.model_fields["device_type"].default,
            location_id=(override.location_id if override else None) or payload.location_id,
            department=(override.department if override else None) or payload.department,
        )
        db.add(device)
        await db.flush()
        r.imported = True
        r.device_id = device.id
        db.add(
            Event(
                device_id=device.id,
                event_type=EventType.DEVICE_DISCOVERED,
                severity=EventSeverity.INFO,
                message=f"Device {device.hostname} ({device.ip_address}) imported from discovery",
            )
        )
        imported.append(r)

    await write_audit(
        db, current_user, "discovery.import", "discovery_job", job_id, {"imported_count": len(imported)}
    )
    await db.commit()
    return imported
