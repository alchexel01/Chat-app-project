from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json, os

from database import Base, engine
from routes import auth, users, chats, media
from ws_manager import manager

Base.metadata.create_all(bind=engine)

app = FastAPI(title="WhatsApp Clone API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router,  prefix="/api/auth",  tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(chats.router, prefix="/api/chats", tags=["Chats"])
app.include_router(media.router, prefix="/api/media", tags=["Media"])


@app.get("/")
def root():
    return {"status": "WhatsApp Clone API running"}


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(websocket, user_id)
    await manager.broadcast_status(user_id, online=True)
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            event = data.get("event")
            if event == "typing":
                await manager.send_typing(
                    from_user_id=user_id,
                    chat_id=data["chat_id"],
                    is_typing=data.get("is_typing", True),
                )
            elif event == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        await manager.broadcast_status(user_id, online=False)