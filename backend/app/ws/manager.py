import logging

from fastapi import WebSocket

logger = logging.getLogger("app.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    def connect(self, websocket: WebSocket) -> None:
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: str) -> None:
        dead: list[WebSocket] = []
        for websocket in self._connections:
            try:
                await websocket.send_text(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self._connections.discard(websocket)


manager = ConnectionManager()
