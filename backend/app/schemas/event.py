import uuid
from datetime import datetime

from nms_common.enums import EventSeverity, EventType

from app.schemas.common import ORMModel


class EventOut(ORMModel):
    id: uuid.UUID
    device_id: uuid.UUID | None
    interface_id: uuid.UUID | None
    event_type: EventType
    severity: EventSeverity
    message: str
    event_metadata: dict
    created_at: datetime
