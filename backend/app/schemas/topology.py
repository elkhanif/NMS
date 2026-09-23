import uuid

from pydantic import BaseModel

from nms_common.enums import DeviceStatus, DeviceType, RelationshipType

from app.schemas.common import ORMModel


class TopologyNode(ORMModel):
    id: uuid.UUID
    hostname: str
    ip_address: str
    device_type: DeviceType
    status: DeviceStatus
    location_id: uuid.UUID | None


class TopologyEdge(ORMModel):
    id: uuid.UUID
    parent_device_id: uuid.UUID
    child_device_id: uuid.UUID
    relationship_type: RelationshipType
    discovered: bool


class TopologyGraph(BaseModel):
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]


class RelationshipCreate(BaseModel):
    parent_device_id: uuid.UUID
    child_device_id: uuid.UUID
    relationship_type: RelationshipType = RelationshipType.DOWNLINK
    parent_interface_id: uuid.UUID | None = None
    child_interface_id: uuid.UUID | None = None
