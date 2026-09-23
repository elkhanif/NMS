import asyncio
import logging
import os
import socket
from datetime import datetime, timezone

from sqlalchemy import select

from nms_common.db import new_session
from nms_common.models import WorkerHeartbeat

from worker.scheduler import Scheduler

logger = logging.getLogger("worker.heartbeat")

HEARTBEAT_INTERVAL = 15
WORKER_NAME = os.environ.get("WORKER_NAME", socket.gethostname())


async def run_forever(scheduler: Scheduler) -> None:
    while True:
        try:
            async with new_session() as db:
                result = await db.execute(select(WorkerHeartbeat).where(WorkerHeartbeat.worker_name == WORKER_NAME))
                heartbeat = result.scalar_one_or_none()
                if heartbeat is None:
                    heartbeat = WorkerHeartbeat(worker_name=WORKER_NAME, last_heartbeat_at=datetime.now(timezone.utc))
                    db.add(heartbeat)
                heartbeat.last_heartbeat_at = datetime.now(timezone.utc)
                heartbeat.active_devices = scheduler.active_devices
                heartbeat.active_polls = scheduler.active_polls
                await db.commit()
        except Exception:
            logger.exception("Failed to write worker heartbeat")
        await asyncio.sleep(HEARTBEAT_INTERVAL)
