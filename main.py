import os
import uuid
import asyncio
from fastapi import FastAPI, Request, Form, HTTPException, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import redis.asyncio as redis
from typing import Dict

# --- Инициализация ---
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Подключение к Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost")
redis_client = redis.from_url(redis_url, decode_responses=True)


# --- Класс для управления WebSocket соединениями ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)

    async def broadcast(self, message: str, room_id: str):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_text(message)

manager = ConnectionManager()


# --- Маршруты HTTP ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.post("/create_pad")
async def create_pad(request: Request):
    room_id = str(uuid.uuid4().hex)[:8]
    await redis_client.set(f"pad:{room_id}:exists", "1", ex=3600)
    return RedirectResponse(url=f"/pad/{room_id}", status_code=303)

@app.get("/pad/{room_id}", response_class=HTMLResponse)
async def get_pad(request: Request, room_id: str):
    if not await redis_client.exists(f"pad:{room_id}:exists"):
        raise HTTPException(status_code=404, detail="Комната не найдена или срок ее действия истек.")
    return templates.TemplateResponse("pad_room.html", {"request": request, "room_id": room_id})


# --- Маршрут WebSocket ---

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """
    Обрабатывает WebSocket соединения для комнат чата. (ИСПРАВЛЕННАЯ ВЕРСИЯ)
    """
    if not await redis_client.exists(f"pad:{room_id}:exists"):
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Просто транслируем полученное сообщение всем в комнате
            await manager.broadcast(data, room_id)
    except Exception:
        manager.disconnect(websocket, room_id)