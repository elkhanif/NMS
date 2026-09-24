import secrets

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from nms_common.ws_events import get_redis

from app.core.cors import ALLOWED_ORIGINS
from app.deps import get_current_user
from app.ws.manager import manager
from nms_common.models import User

router = APIRouter(tags=["ws"])

WS_TICKET_TTL_SECONDS = 30


@router.post("/ws/ticket")
async def issue_ws_ticket(user: User = Depends(get_current_user)) -> dict:
    """One-time, short-lived ticket so the browser can authenticate a raw WebSocket
    connection without ever seeing the JWT (a WebSocket can't set an Authorization
    header, and this endpoint is reached through the same authenticated Next.js proxy
    as every other API call)."""
    ticket = secrets.token_urlsafe(32)
    redis = get_redis()
    await redis.set(f"ws_ticket:{ticket}", str(user.id), ex=WS_TICKET_TTL_SECONDS)
    return {"ticket": ticket}


@router.websocket("/ws")
async def live_updates(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in ALLOWED_ORIGINS:
        await websocket.close(code=1008)
        return

    ticket = websocket.query_params.get("ticket")
    if not ticket:
        await websocket.close(code=1008)
        return

    redis = get_redis()
    user_id = await redis.getdel(f"ws_ticket:{ticket}")
    if user_id is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
