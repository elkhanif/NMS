import uuid
from datetime import datetime

from pydantic import BaseModel

from nms_common.enums import IncidentConfidence, IncidentStatus

from app.schemas.common import ORMModel
from app.schemas.device import DeviceOut
from app.schemas.event import EventOut
from app.schemas.topology import TopologyGraph


class IncidentOut(ORMModel):
    id: uuid.UUID
    sequence_number: int
    suspected_device_id: uuid.UUID | None
    status: IncidentStatus
    confidence: IncidentConfidence
    title: str
    started_at: datetime
    detected_at: datetime
    resolved_at: datetime | None
    affected_device_count: int
    created_at: datetime
    updated_at: datetime


class IncidentDetailOut(IncidentOut):
    suspected_device: DeviceOut | None = None
    affected_devices: list[DeviceOut] = []
    related_events: list[EventOut] = []
    duration_seconds: float | None = None
    topology: TopologyGraph


class IncidentPatch(BaseModel):
    """Human-in-the-loop overrides -- confidence=CONFIRMED is only ever set here,
    never by the correlator itself."""

    confidence: IncidentConfidence | None = None
    suspected_device_id: uuid.UUID | None = None
    status: IncidentStatus | None = None
