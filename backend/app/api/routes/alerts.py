import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.enums import AlertSeverity, AlertStatus, EventSeverity, EventType
from nms_common.models import Alert, Event, User

from app.deps import get_current_user, get_db, require_operator
from app.schemas.alert import AlertOut
from app.services.audit import write_audit

router = APIRouter(prefix="/alerts", tags=["alerts"], dependencies=[Depends(get_current_user)])


@router.get("/", response_model=list[AlertOut])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    status_filter: AlertStatus | None = Query(default=None, alias="status"),
    severity: AlertSeverity | None = None,
    device_id: uuid.UUID | None = None,
    limit: int = Query(default=200, le=1000),
) -> list[Alert]:
    stmt = select(Alert)
    if status_filter:
        stmt = stmt.where(Alert.status == status_filter)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if device_id:
        stmt = stmt.where(Alert.device_id == device_id)
    stmt = stmt.order_by(Alert.opened_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.patch("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_operator)
) -> Alert:
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if alert.status != AlertStatus.OPEN:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only OPEN alerts can be acknowledged")

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_by_id = current_user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.add(
        Event(
            device_id=alert.device_id,
            event_type=EventType.ALERT_ACKNOWLEDGED,
            severity=EventSeverity.INFO,
            message=f"Alert '{alert.message}' acknowledged by {current_user.email}",
        )
    )
    await write_audit(db, current_user, "alert.acknowledge", "alert", alert_id)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.patch("/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_operator)
) -> Alert:
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Alert already resolved")

    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now(timezone.utc)
    db.add(
        Event(
            device_id=alert.device_id,
            event_type=EventType.ALERT_RESOLVED,
            severity=EventSeverity.INFO,
            message=f"Alert '{alert.message}' manually resolved by {current_user.email}",
        )
    )
    await write_audit(db, current_user, "alert.resolve", "alert", alert_id)
    await db.commit()
    await db.refresh(alert)
    return alert
