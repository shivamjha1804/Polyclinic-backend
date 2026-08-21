from collections import defaultdict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        if websocket in self.active_connections.get(user_id, []):
            self.active_connections[user_id].remove(websocket)

        if not self.active_connections.get(user_id):
            self.active_connections.pop(user_id, None)

    async def notify(self, user_id: str, message: dict):
        for ws in list(self.active_connections.get(user_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()