"""Periodic sweep (same run_forever-every-N-seconds pattern as discovery.py) that
emits exactly one DEVICE_MISSING event per continuous outage once a device has been
DOWN for longer than `device_missing_after_seconds` -- distinct from the immediate
DEVICE_DOWN event collectors.py emits the moment a device first stops responding.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.config import get_settings
from nms_common.db import new_session
from nms_common.enums import DeviceStatus, EventSeverity, EventType
from nms_common.models import Device, DeviceStateHistory, Event

logger = logging.getLogger("worker.reconciliation")


async def run_forever() -> None:
    settings = get_settings()
    while True:
        try:
            await _sweep()
        except Exception:
            logger.exception("Reconciliation sweep error")
        await asyncio.sleep(settings.reconciliation_sweep_interval_seconds)


async def _sweep() -> None:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.device_missing_after_seconds)

    async with new_session() as db:
        result = await db.execute(select(Device).where(Device.status == DeviceStatus.DOWN))
        for device in result.scalars().all():
            await _maybe_flag_missing(db, device, cutoff, settings.device_missing_after_seconds)
        await db.commit()


async def _maybe_flag_missing(db: AsyncSession, device: Device, cutoff: datetime, after_seconds: int) -> None:
    last_transition_result = await db.execute(
        select(DeviceStateHistory)
        .where(DeviceStateHistory.device_id == device.id)
        .order_by(DeviceStateHistory.changed_at.desc())
        .limit(1)
    )
    last_transition = last_transition_result.scalar_one_or_none()
    if last_transition is None or last_transition.new_status != DeviceStatus.DOWN:
        return  # status flipped again since the query above, or no history yet
    if last_transition.changed_at > cutoff:
        return  # hasn't been down long enough yet

    already_flagged_result = await db.execute(
        select(Event.id)
        .where(
            Event.device_id == device.id,
            Event.event_type == EventType.DEVICE_MISSING,
            Event.created_at >= last_transition.changed_at,
        )
        .limit(1)
    )
    if already_flagged_result.scalar_one_or_none() is not None:
        return  # already flagged this same continuous outage

    db.add(
        Event(
            device_id=device.id,
            event_type=EventType.DEVICE_MISSING,
            severity=EventSeverity.WARNING,
            message=f"{device.hostname} ({device.ip_address}) has been unreachable for over "
            f"{after_seconds // 60} minutes",
            event_metadata={"down_since": last_transition.changed_at.isoformat()},
        )
    )
