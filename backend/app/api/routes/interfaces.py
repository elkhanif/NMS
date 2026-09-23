import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.enums import InterfaceStatus
from nms_common.models import Interface, InterfaceMetric, User

from app.deps import get_current_user, get_db
from app.schemas.device import InterfaceOut
from app.schemas.metric import InterfaceMetricPoint

router = APIRouter(prefix="/interfaces", tags=["interfaces"], dependencies=[Depends(get_current_user)])


@router.get("/", response_model=list[InterfaceOut])
async def list_interfaces(
    db: AsyncSession = Depends(get_db),
    device_id: uuid.UUID | None = None,
    oper_status: InterfaceStatus | None = None,
    limit: int = Query(default=500, le=2000),
) -> list[Interface]:
    stmt = select(Interface)
    if device_id:
        stmt = stmt.where(Interface.device_id == device_id)
    if oper_status:
        stmt = stmt.where(Interface.oper_status == oper_status)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{interface_id}/metrics", response_model=list[InterfaceMetricPoint])
async def get_interface_metrics(
    interface_id: uuid.UUID, hours: int = Query(default=24, le=24 * 30), db: AsyncSession = Depends(get_db)
) -> list[InterfaceMetric]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(InterfaceMetric)
        .where(InterfaceMetric.interface_id == interface_id, InterfaceMetric.time >= since)
        .order_by(InterfaceMetric.time)
    )
    return list(result.scalars().all())
