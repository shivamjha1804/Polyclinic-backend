from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.db.client import supabase_admin
from app.services.realtime import manager

router = APIRouter()

@router.websocket("/ws/notifications")
async def notifocation_ws(websocket: WebSocket, token: str = Query(...)):
    try:
        user = supabase_admin.auth.get_user(token).user
    except Exception:
        await websocket.close(code=1008)
        return

    if user is None:
        await websocket.close(code=1008)
        return

    user_id = user.id
    await manager.connect(user_id, websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)