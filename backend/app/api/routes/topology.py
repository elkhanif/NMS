import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.models import Device, DeviceRelationship, User

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
    edge = DeviceRelationship(**payload.model_dump())
    db.add(edge)
    await db.flush()
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
