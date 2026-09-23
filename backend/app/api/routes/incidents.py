import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.enums import IncidentConfidence, IncidentStatus
from nms_common.models import Device, DeviceRelationship, Event, Incident, IncidentEvent, User

from app.deps import get_current_user, get_db, require_config_writer
from app.schemas.device import DeviceOut
from app.schemas.event import EventOut
from app.schemas.incident import IncidentDetailOut, IncidentOut, IncidentPatch
from app.schemas.topology import TopologyEdge, TopologyGraph, TopologyNode
from app.services.audit import write_audit

router = APIRouter(prefix="/incidents", tags=["incidents"], dependencies=[Depends(get_current_user)])


@router.get("/", response_model=list[IncidentOut])
async def list_incidents(
    db: AsyncSession = Depends(get_db),
    status_filter: IncidentStatus | None = Query(default=None, alias="status"),
    confidence: IncidentConfidence | None = None,
    device_id: uuid.UUID | None = None,
    limit: int = Query(default=100, le=500),
) -> list[Incident]:
    stmt = select(Incident)
    if status_filter:
        stmt = stmt.where(Incident.status == status_filter)
    if confidence:
        stmt = stmt.where(Incident.confidence == confidence)
    if device_id:
        stmt = stmt.where(Incident.suspected_device_id == device_id)
    stmt = stmt.order_by(Incident.detected_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{incident_id}", response_model=IncidentDetailOut)
async def get_incident(incident_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> IncidentDetailOut:
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    ie_result = await db.execute(select(IncidentEvent).where(IncidentEvent.incident_id == incident_id))
    event_ids = [ie.event_id for ie in ie_result.scalars().all()]
    events: list[Event] = []
    if event_ids:
        events_result = await db.execute(select(Event).where(Event.id.in_(event_ids)).order_by(Event.created_at))
        events = list(events_result.scalars().all())

    device_ids = {e.device_id for e in events if e.device_id is not None}
    if incident.suspected_device_id:
        device_ids.add(incident.suspected_device_id)
    devices: list[Device] = []
    if device_ids:
        devices_result = await db.execute(select(Device).where(Device.id.in_(device_ids)))
        devices = list(devices_result.scalars().all())

    suspected_device = next((d for d in devices if d.id == incident.suspected_device_id), None)

    duration_seconds = None
    if incident.resolved_at:
        duration_seconds = (incident.resolved_at - incident.started_at).total_seconds()
    elif incident.status == IncidentStatus.OPEN:
        duration_seconds = (datetime.now(timezone.utc) - incident.started_at).total_seconds()

    edges: list[DeviceRelationship] = []
    if device_ids:
        edges_result = await db.execute(
            select(DeviceRelationship).where(
                DeviceRelationship.parent_device_id.in_(device_ids)
                | DeviceRelationship.child_device_id.in_(device_ids)
            )
        )
        edges = list(edges_result.scalars().all())

    return IncidentDetailOut(
        id=incident.id,
        sequence_number=incident.sequence_number,
        suspected_device_id=incident.suspected_device_id,
        status=incident.status,
        confidence=incident.confidence,
        title=incident.title,
        started_at=incident.started_at,
        detected_at=incident.detected_at,
        resolved_at=incident.resolved_at,
        affected_device_count=incident.affected_device_count,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        suspected_device=DeviceOut.model_validate(suspected_device) if suspected_device else None,
        affected_devices=[DeviceOut.model_validate(d) for d in devices],
        related_events=[EventOut.model_validate(e) for e in events],
        duration_seconds=duration_seconds,
        topology=TopologyGraph(
            nodes=[TopologyNode.model_validate(d) for d in devices],
            edges=[TopologyEdge.model_validate(e) for e in edges],
        ),
    )


@router.patch("/{incident_id}", response_model=IncidentOut)
async def update_incident(
    incident_id: uuid.UUID,
    payload: IncidentPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> Incident:
    """Human-in-the-loop overrides only -- this is the only code path that may ever
    set confidence=CONFIRMED or force a status/suspected-device change."""
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(incident, field, value)
    if data.get("status") == IncidentStatus.RESOLVED and incident.resolved_at is None:
        incident.resolved_at = datetime.now(timezone.utc)

    await write_audit(db, current_user, "incident.update", "incident", incident_id, data)
    await db.commit()
    await db.refresh(incident)
    return incident
