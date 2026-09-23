"""Basic, rule-based incident correlation (not ML): groups a device's DEVICE_DOWN
event with its topology children's own DEVICE_DOWN events into one Incident instead
of raising N independent alerts for what's probably one shared-cause outage.

Deliberately conservative: an incident is only ever POSSIBLE or SUSPECTED, and this
module never sets CONFIRMED -- that's a human-only action via PATCH /incidents/{id}
(see backend/app/api/routes/incidents.py). Correlation is entirely gated on
`device_relationships` existing between the affected devices: nothing here infers a
shared cause from a shared gateway or shared access point unless/until that
relationship is actually modeled, so a real shared-cause outage between two
unrelated-on-paper devices will simply show as independent events, same as today --
never a fabricated link.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.config import get_settings
from nms_common.db import new_session
from nms_common.enums import (
    DeviceStatus,
    EventType,
    IncidentConfidence,
    IncidentEventRole,
    IncidentStatus,
)
from nms_common.models import Device, DeviceCheck, DeviceRelationship, Event, Incident, IncidentEvent

logger = logging.getLogger("worker.correlator")


async def run_forever() -> None:
    settings = get_settings()
    while True:
        try:
            await _sweep()
        except Exception:
            logger.exception("Correlation sweep error")
        await asyncio.sleep(settings.correlation_sweep_interval_seconds)


async def _sweep() -> None:
    async with new_session() as db:
        await _correlate_new_down_events(db)
        await _auto_resolve(db)
        await db.commit()


async def _is_linked(db: AsyncSession, event_id: uuid.UUID) -> bool:
    result = await db.execute(select(IncidentEvent.id).where(IncidentEvent.event_id == event_id).limit(1))
    return result.scalar_one_or_none() is not None


async def _children_of(db: AsyncSession, device_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.execute(
        select(DeviceRelationship.child_device_id).where(DeviceRelationship.parent_device_id == device_id)
    )
    return [row[0] for row in result.all()]


async def _parents_of(db: AsyncSession, device_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.execute(
        select(DeviceRelationship.parent_device_id).where(DeviceRelationship.child_device_id == device_id)
    )
    return [row[0] for row in result.all()]


async def _find_ancestor_open_incident(
    db: AsyncSession, device_id: uuid.UUID, _depth: int = 0
) -> Incident | None:
    """If `device_id` is downstream of a device that already suspects an open
    incident, returns that incident so a cascading multi-level outage attaches to
    one incident instead of spawning a new one per hop. Depth-capped defensively in
    case of a topology cycle."""
    if _depth > 10:
        return None
    for parent_id in await _parents_of(db, device_id):
        result = await db.execute(
            select(Incident).where(Incident.suspected_device_id == parent_id, Incident.status == IncidentStatus.OPEN)
        )
        incident = result.scalar_one_or_none()
        if incident is not None:
            return incident
        ancestor = await _find_ancestor_open_incident(db, parent_id, _depth + 1)
        if ancestor is not None:
            return ancestor
    return None


async def _max_check_interval(db: AsyncSession, device_ids: list[uuid.UUID]) -> int:
    if not device_ids:
        return 0
    result = await db.execute(select(DeviceCheck.interval_seconds).where(DeviceCheck.device_id.in_(device_ids)))
    intervals = [row[0] for row in result.all()]
    return max(intervals) if intervals else 0


async def _correlate_new_down_events(db: AsyncSession) -> None:
    settings = get_settings()
    lookback = datetime.now(timezone.utc) - timedelta(seconds=max(settings.correlation_window_seconds * 4, 600))

    result = await db.execute(
        select(Event)
        .where(Event.event_type == EventType.DEVICE_DOWN, Event.created_at >= lookback)
        .order_by(Event.created_at)
    )

    for down_event in result.scalars().all():
        if down_event.device_id is None or await _is_linked(db, down_event.id):
            continue

        child_ids = await _children_of(db, down_event.device_id)
        if not child_ids:
            continue  # a lone outage with no modeled dependents is never wrapped in an incident

        # Correlation window scales to the slowest relevant child's poll interval --
        # a fixed window would under-count children on slow-interval checks.
        window_seconds = max(settings.correlation_window_seconds, await _max_check_interval(db, child_ids))
        window_end = down_event.created_at + timedelta(seconds=window_seconds)

        window_start = down_event.created_at - timedelta(seconds=window_seconds)
        child_down_result = await db.execute(
            select(Event).where(
                Event.event_type == EventType.DEVICE_DOWN,
                Event.device_id.in_(child_ids),
                Event.created_at >= window_start,
                Event.created_at <= window_end,
            )
        )
        correlated_children = [e for e in child_down_result.scalars().all() if not await _is_linked(db, e.id)]
        if not correlated_children:
            continue

        confidence = (
            IncidentConfidence.SUSPECTED
            if len(correlated_children) >= settings.correlation_min_children_for_suspected
            else IncidentConfidence.POSSIBLE
        )
        affected_delta = len(correlated_children) + 1

        ancestor_incident = await _find_ancestor_open_incident(db, down_event.device_id)
        if ancestor_incident is not None:
            incident = ancestor_incident
            incident.affected_device_count += affected_delta
            if confidence == IncidentConfidence.SUSPECTED:
                incident.confidence = IncidentConfidence.SUSPECTED
        else:
            existing_result = await db.execute(
                select(Incident).where(
                    Incident.suspected_device_id == down_event.device_id,
                    Incident.status == IncidentStatus.OPEN,
                )
            )
            incident = existing_result.scalar_one_or_none()
            if incident is None:
                device = await db.get(Device, down_event.device_id)
                label = "Suspected" if confidence == IncidentConfidence.SUSPECTED else "Possible"
                incident = Incident(
                    suspected_device_id=down_event.device_id,
                    status=IncidentStatus.OPEN,
                    confidence=confidence,
                    title=f"{label} network incident: {device.hostname if device else 'Unknown device'}",
                    started_at=down_event.created_at,
                    root_event_id=down_event.id,
                    affected_device_count=affected_delta,
                )
                db.add(incident)
                await db.flush()
            else:
                incident.affected_device_count += affected_delta
                if confidence == IncidentConfidence.SUSPECTED:
                    incident.confidence = IncidentConfidence.SUSPECTED

        db.add(IncidentEvent(incident_id=incident.id, event_id=down_event.id, role=IncidentEventRole.TRIGGER))
        for child_event in correlated_children:
            db.add(IncidentEvent(incident_id=incident.id, event_id=child_event.id, role=IncidentEventRole.AFFECTED))
        await db.flush()


async def _incident_device_ids(db: AsyncSession, incident_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.execute(
        select(Event.device_id)
        .join(IncidentEvent, IncidentEvent.event_id == Event.id)
        .where(IncidentEvent.incident_id == incident_id, IncidentEvent.role != IncidentEventRole.RECOVERY)
    )
    return [row[0] for row in result.all() if row[0] is not None]


async def _auto_resolve(db: AsyncSession) -> None:
    result = await db.execute(select(Incident).where(Incident.status == IncidentStatus.OPEN))
    for incident in result.scalars().all():
        device_ids = await _incident_device_ids(db, incident.id)
        if not device_ids:
            continue

        devices_result = await db.execute(select(Device).where(Device.id.in_(device_ids)))
        devices = list(devices_result.scalars().all())
        if any(d.status == DeviceStatus.DOWN for d in devices):
            continue  # still ongoing

        recovered_at = datetime.now(timezone.utc)
        recovery_result = await db.execute(
            select(Event)
            .where(Event.event_type == EventType.DEVICE_RECOVERED, Event.device_id.in_(device_ids))
            .order_by(Event.created_at.desc())
        )
        recovery_events = list(recovery_result.scalars().all())
        if recovery_events:
            recovered_at = max(e.created_at for e in recovery_events)
            for event in recovery_events:
                if not await _is_linked(db, event.id):
                    db.add(IncidentEvent(incident_id=incident.id, event_id=event.id, role=IncidentEventRole.RECOVERY))

        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = recovered_at
