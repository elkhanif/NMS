import asyncio
import logging

from sqlalchemy import text

from nms_common.db import get_engine

from worker import discovery, heartbeat, reconciliation
from worker.scheduler import Scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("worker.main")


async def _wait_for_database(retries: int = 30, delay: float = 2.0) -> None:
    engine = get_engine()
    for attempt in range(1, retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database is reachable")
            return
        except Exception as exc:
            logger.warning("Database not ready yet (attempt %s/%s): %s", attempt, retries, exc)
            await asyncio.sleep(delay)
    raise RuntimeError("Database never became reachable")


async def main() -> None:
    await _wait_for_database()

    scheduler = Scheduler()
    logger.info("Starting monitoring worker: max_concurrent_polls=%s", scheduler.settings.max_concurrent_polls)

    await asyncio.gather(
        scheduler.run_forever(),
        heartbeat.run_forever(scheduler),
        discovery.run_forever(),
        reconciliation.run_forever(),
    )


if __name__ == "__main__":
    asyncio.run(main())
