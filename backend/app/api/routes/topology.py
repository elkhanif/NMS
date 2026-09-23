import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.enums import EventSeverity, EventType
from nms_common.models import Device, DeviceRelationship, Event, Interface, User

from app.deps import get_current_user, get_db, require_config_writer
from app.schemas.topology import RelationshipCreate, TopologyEdge, TopologyGraph, TopologyNode
from app.services.audit import write_audit

router = APIRouter(prefix="/topology", tags=["topology"], dependencies=[Depends(get_current_user)])


@router.get("/", response_model=TopologyGraph)
async def get_topology(db: AsyncSession = Depends(get_db)) -> TopologyGraph:
    devices_result = await db.execute(select(Device))
    devices = list(devices_result.scalars().all())

    edges_result = await db.execute(select(DeviceRelationship))
    edges = list(edges_result.scalars().all())

    return TopologyGraph(
        nodes=[TopologyNode.model_validate(d) for d in devices],
        edges=[TopologyEdge.model_validate(e) for e in edges],
    )


@router.post("/relationships", response_model=TopologyEdge, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    payload: RelationshipCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> DeviceRelationship:
    # Admin-triggered, so this is 100% accurate (no inference): if the child device
    # already had a different parent/port on record, this new edge represents it
    # moving -- surface that as a SWITCH_PORT_CHANGED event before adding the new one.
    existing_result = await db.execute(
        select(DeviceRelationship).where(DeviceRelationship.child_device_id == payload.child_device_id)
    )
    prior = next(
        (
            e
            for e in existing_result.scalars().all()
            if e.parent_device_id != payload.parent_device_id or e.child_interface_id != payload.child_interface_id
        ),
        None,
    )

    edge = DeviceRelationship(**payload.model_dump())
    db.add(edge)
    await db.flush()

    if prior is not None:
        child_device, old_parent, new_parent = (
            await db.get(Device, payload.child_device_id),
            await db.get(Device, prior.parent_device_id),
            await db.get(Device, payload.parent_device_id),
        )
        old_iface = await db.get(Interface, prior.child_interface_id) if prior.child_interface_id else None
        new_iface = await db.get(Interface, payload.child_interface_id) if payload.child_interface_id else None
        old_label = f"{old_parent.hostname if old_parent else 'Unknown'}/{old_iface.name if old_iface else 'Unknown'}"
        new_label = f"{new_parent.hostname if new_parent else 'Unknown'}/{new_iface.name if new_iface else 'Unknown'}"
        db.add(
            Event(
                device_id=payload.child_device_id,
                event_type=EventType.SWITCH_PORT_CHANGED,
                severity=EventSeverity.INFO,
                message=f"{child_device.hostname if child_device else 'Device'} connection changed: "
                f"{old_label} -> {new_label}",
                event_metadata={
                    "old_parent_device_id": str(prior.parent_device_id),
                    "old_interface_id": str(prior.child_interface_id) if prior.child_interface_id else None,
                    "new_parent_device_id": str(payload.parent_device_id),
                    "new_interface_id": str(payload.child_interface_id) if payload.child_interface_id else None,
                },
            )
        )
        # The child now belongs to exactly one parent/port -- remove the stale
        # edge so topology/correlation/detective queries can't nondeterministically
        # resolve to the device's old (no-longer-true) parent.
        await db.delete(prior)

    await write_audit(db, current_user, "topology.relationship.create", "device_relationship", edge.id)
    await db.commit()
    return edge


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relationship(
    relationship_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_config_writer),
) -> None:
    edge = await db.get(DeviceRelationship, relationship_id)
    if edge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    await db.delete(edge)
    await write_audit(db, current_user, "topology.relationship.delete", "device_relationship", relationship_id)
    await db.commit()
