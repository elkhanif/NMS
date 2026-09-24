import json
import threading
import uuid

import pytest
import redis as redis_sync
from starlette.testclient import TestClient

import nms_common.ws_events as ws_events
from nms_common.config import get_settings
from nms_common.enums import UserRole
from nms_common.models import User
from nms_common.ws_events import CHANNEL

from app.deps import get_current_user
from app.main import app

FAKE_USER = User(
    id=uuid.uuid4(),
    email="ws-test@test.com",
    hashed_password="x",
    role=UserRole.ADMIN,
    is_active=True,
)


async def test_ws_ticket_requires_auth(client):
    resp = await client.post("/api/v1/ws/ticket")
    assert resp.status_code == 401


async def test_ws_ticket_issued_for_authenticated_user(client, admin_token):
    resp = await client.post("/api/v1/ws/ticket", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert "ticket" in resp.json()


@pytest.fixture
def ws_test_client():
    """The websocket route only ever talks to Redis (never the DB), so it's safe to
    exercise via Starlette's synchronous TestClient (its own event loop/thread) --
    unlike the httpx `client` fixture used elsewhere, which shares the DB fixtures'
    event loop and can't touch DB-backed routes safely from here.

    Each TestClient spins up its own fresh event loop; `nms_common.ws_events`'s
    module-level Redis singleton would otherwise survive across tests still bound to
    a previous (now-dead) loop, silently killing the lifespan's subscriber task. Only
    a test-isolation concern -- a real deployment only ever has one loop for the
    process's lifetime."""
    ws_events._redis = None
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.pop(get_current_user, None)
    ws_events._redis = None


def test_ws_rejects_missing_ticket(ws_test_client):
    with pytest.raises(Exception):
        with ws_test_client.websocket_connect("/api/v1/ws"):
            pass


def test_ws_rejects_invalid_ticket(ws_test_client):
    with pytest.raises(Exception):
        with ws_test_client.websocket_connect("/api/v1/ws?ticket=not-a-real-ticket"):
            pass


def test_ws_accepts_valid_ticket_and_receives_broadcast(ws_test_client):
    ticket_resp = ws_test_client.post("/api/v1/ws/ticket")
    assert ticket_resp.status_code == 200
    ticket = ticket_resp.json()["ticket"]

    with ws_test_client.websocket_connect(f"/api/v1/ws?ticket={ticket}") as ws:
        # Published with a plain synchronous redis client -- deliberately not
        # `nms_common.ws_events.get_redis()`'s asyncio singleton, which is bound to
        # this app's own event loop; a sync client has no loop affinity, same as the
        # separate worker process that publishes this in production.
        publisher = redis_sync.Redis.from_url(get_settings().redis_url, decode_responses=True)
        payload = json.dumps({"type": "event", "action": "created", "device_id": str(uuid.uuid4())})

        # `receive_text()` blocks with no timeout parameter in Starlette's TestClient,
        # so bound the wait with a thread join instead of risking a hung test.
        received: list[str] = []

        def _receive():
            received.append(ws.receive_text())

        receiver = threading.Thread(target=_receive, daemon=True)
        receiver.start()
        publisher.publish(CHANNEL, payload)
        receiver.join(timeout=5)

        assert received, "did not receive the broadcast message within 5s"
        assert json.loads(received[0])["action"] == "created"
