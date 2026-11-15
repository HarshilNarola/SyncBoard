from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from ..database import SessionLocal
from ..models import BoardMember
from ..security import decode_token
from ..websocket_manager import manager


router = APIRouter()


@router.websocket("/ws/boards/{board_id}")
async def board_websocket(websocket: WebSocket, board_id: int) -> None:
    token = websocket.query_params.get("token")
    user_id = decode_token(token) if token else None
    if user_id is None:
        await websocket.close(code=1008)
        return
    with SessionLocal() as db:
        is_member = db.scalar(
            select(BoardMember.id).where(BoardMember.board_id == board_id, BoardMember.user_id == user_id)
        )
    if is_member is None:
        await websocket.close(code=1008)
        return
    await manager.connect(board_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(board_id, websocket)
