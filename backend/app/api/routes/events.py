import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.enums import EventSeverity, EventType
from nms_common.models import Event

from app.deps import get_current_user, get_db
from app.schemas.event import EventOut

router = APIRouter(prefix="/events", tags=["events"], dependencies=[Depends(get_current_user)])


@router.get("/", response_model=list[EventOut])
async def list_events(
    db: AsyncSession = Depends(get_db),
    device_id: uuid.UUID | None = None,
    event_type: EventType | None = None,
    severity: EventSeverity | None = None,
    limit: int = Query(default=200, le=1000),
) -> list[Event]:
    stmt = select(Event)
    if device_id:
        stmt = stmt.where(Event.device_id == device_id)
    if event_type:
        stmt = stmt.where(Event.event_type == event_type)
    if severity:
        stmt = stmt.where(Event.severity == severity)
    stmt = stmt.order_by(Event.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
