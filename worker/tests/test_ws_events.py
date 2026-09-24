import asyncio
import json
import uuid

from nms_common.ws_events import CHANNEL, get_redis, publish_pending, queue_event


async def test_queue_event_publishes_after_commit_only(db_session):
    device_id = uuid.uuid4()
    queue_event(db_session, "event", "created", device_id=device_id, event_type="DEVICE_DOWN")
    assert db_session.info["ws_events"] == [
        {
            "type": "event",
            "action": "created",
            "ts": db_session.info["ws_events"][0]["ts"],
            "device_id": str(device_id),
            "event_type": "DEVICE_DOWN",
        }
    ]

    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)
    try:
        await asyncio.sleep(0.05)  # let the subscription register before we publish
        await publish_pending(db_session)

        message = None
        for _ in range(20):
            message = await pubsub.get_message(timeout=0.5)
            if message and message["type"] == "message":
                break
        assert message is not None and message["type"] == "message"
        body = json.loads(message["data"])
        assert body["type"] == "event"
        assert body["action"] == "created"
        assert body["device_id"] == str(device_id)
    finally:
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.aclose()

    assert "ws_events" not in db_session.info


async def test_publish_pending_is_a_noop_with_nothing_queued(db_session):
    assert "ws_events" not in db_session.info
    await publish_pending(db_session)  # must not raise
