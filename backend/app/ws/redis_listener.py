import asyncio
import logging

from nms_common.ws_events import CHANNEL, get_redis

from app.ws.manager import ConnectionManager

logger = logging.getLogger("app.ws")


async def listen(manager: ConnectionManager) -> None:
    """Subscribes to the worker's Redis pub/sub channel and fans each message out to
    every connected browser WebSocket. Runs for the app's lifetime as a background
    task started from `main.py`'s lifespan."""
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                await manager.broadcast(message["data"])
            except Exception:
                logger.exception("Failed broadcasting a live-update message")
    except asyncio.CancelledError:
        raise
    finally:
        await pubsub.unsubscribe(CHANNEL)
