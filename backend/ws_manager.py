from fastapi import WebSocket
from typing import Dict
import json


class ConnectionManager:
    def __init__(self):
        self.active: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active[user_id] = websocket

    def disconnect(self, user_id: int):
        self.active.pop(user_id, None)

    async def send_to(self, user_id: int, payload: dict):
        ws = self.active.get(user_id)
        if ws:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                self.disconnect(user_id)

    async def broadcast_to_users(self, user_ids: list[int], payload: dict):
        for uid in user_ids:
            await self.send_to(uid, payload)

    async def broadcast_status(self, user_id: int, online: bool):
        payload = {"event": "user_status", "user_id": user_id, "online": online}
        for uid, ws in list(self.active.items()):
            if uid != user_id:
                try:
                    await ws.send_text(json.dumps(payload))
                except Exception:
                    self.disconnect(uid)

    async def send_typing(self, from_user_id: int, chat_id: int, is_typing: bool):
        payload = {
            "event": "typing",
            "chat_id": chat_id,
            "user_id": from_user_id,
            "is_typing": is_typing,
        }
        for uid, ws in list(self.active.items()):
            if uid != from_user_id:
                try:
                    await ws.send_text(json.dumps(payload))
                except Exception:
                    self.disconnect(uid)


manager = ConnectionManager()