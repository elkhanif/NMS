import json
import uuid
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nms_common.config import get_settings

CHANNEL = "nms:live"

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def queue_event(db: AsyncSession, type_: str, action: str, **fields: Any) -> None:
    """Queues a small push-notification payload on the session, to be published to
    Redis only once `publish_pending` runs after a successful commit -- never before,
    so a rolled-back write can never announce a change that didn't happen."""
    payload: dict[str, Any] = {
        "type": type_,
        "action": action,
        "ts": datetime.now(timezone.utc).isoformat(),
        **{k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in fields.items()},
    }
    db.info.setdefault("ws_events", []).append(payload)


async def publish_pending(db: AsyncSession) -> None:
    events = db.info.pop("ws_events", None)
    if not events:
        return
    redis = get_redis()
    for event in events:
        await redis.publish(CHANNEL, json.dumps(event))
