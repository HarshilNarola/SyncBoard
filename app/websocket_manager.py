import asyncio
from collections import defaultdict

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, board_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.rooms[board_id].add(websocket)

    async def disconnect(self, board_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self.rooms[board_id].discard(websocket)
            if not self.rooms[board_id]:
                self.rooms.pop(board_id, None)

    async def broadcast(self, board_id: int, message: dict) -> None:
        async with self._lock:
            connections = list(self.rooms.get(board_id, set()))
        for connection in connections:
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                await self.disconnect(board_id, connection)


manager = ConnectionManager()
