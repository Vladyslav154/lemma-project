import os
import uuid
import json
import asyncio
from typing import Dict, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, WebSocket, WebSocketDisconnect, Query, Path
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
from fastapi.concurrency import run_in_threadpool
import time
import redis.asyncio as redis

# --- Конфигурация ---
load_dotenv()
app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
redis_url = os.getenv("REDIS_URL")
cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Словарь переводов ---
translations = {
    "ru": { "app_title": "Lepko", "app_subtitle": "Простые инструменты для простых задач.", "upgrade_link": "Получить Pro", "activate_key": "Активировать ключ", "drop_title": "Файлообменник", "drop_description": "Быстрая и анонимная передача файлов.", "pad_title": "Чат-комнаты", "pad_description": "Создайте анонимную комнату для общения.", "home_button": "Домой", "join_title": "Войти по рукопожатию", "join_subtitle": "Наведите камеру на QR-код или перейдите по одноразовой ссылке."},
    "en": { "app_title": "Lepko", "app_subtitle": "Simple tools for simple tasks.", "upgrade_link": "Get Pro", "activate_key": "Activate Key", "drop_title": "File Drop", "drop_description": "Fast and anonymous file transfer.", "pad_title": "Chat Rooms", "pad_description": "Create an anonymous room for communication.", "home_button": "Home", "join_title": "Join by Handshake", "join_subtitle": "Point your camera at the QR code or use the one-time link."}
}

# --- Менеджер подключений чата ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        self.active_connections.setdefault(room_id, []).append(websocket)
    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections and websocket in self.active_connections[room_id]:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
    async def broadcast(self, message: str, room_id: str, sender: WebSocket):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                if connection != sender: await connection.send_text(message)
manager = ConnectionManager()

# --- Модели данных для API ---
class PulseRequest(BaseModel):
    pulse_id: str

# --- Эндпоинты ---
@app.get("/manifest.json", include_in_schema=False)
async def get_manifest(): return FileResponse(os.path.join(BASE_DIR, "manifest.json"))
@app.get("/service-worker.js", include_in_schema=False)
async def get_service_worker(): return FileResponse(os.path.join(BASE_DIR, "service-worker.js"))

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, lang: str = Query("ru", regex="ru|en")):
    def t(key: str) -> str: return translations.get(lang, {}).get(key, key)
    return templates.TemplateResponse("index.html", {"request": request, "t": t, "lang": lang})

@app.get("/join", response_class=HTMLResponse)
async def join_page(request: Request, lang: str = Query("ru", regex="ru|en")):
    def t(key: str) -> str: return translations.get(lang, {}).get(key, key)
    return templates.TemplateResponse("join.html", {"request": request, "t": t, "lang": lang})

@app.get("/join/{pulse_id}")
async def join_via_link(pulse_id: str, lang: str = Query("ru", regex="ru|en")):
    r = redis.from_url(redis_url, decode_responses=True)
    room_id = await r.get(f"pulse:{pulse_id}")
    if not room_id:
        raise HTTPException(status_code=404, detail="Invite link is invalid or has expired.")
    await r.delete(f"pulse:{pulse_id}")
    await r.close()
    return RedirectResponse(url=f"/pad/{room_id}?lang={lang}")

# Этот эндпоинт создает новую комнату и перенаправляет на нее
@app.get("/pad")
async def create_pad_and_redirect(lang: str = Query("ru", regex="ru|en")):
    room_id = str(uuid.uuid4().hex[:8])
    return RedirectResponse(url=f"/pad/{room_id}?lang={lang}")
    
@app.get("/pad/{room_id}", response_class=HTMLResponse)
async def pad_room(request: Request, room_id: str, lang: str = Query("ru", regex="ru|en")):
    def t(key: str) -> str: return translations.get(lang, {}).get(key, key)
    return templates.TemplateResponse("pad_room.html", {"request": request, "room_id": room_id, "t": t, "lang": lang})

@app.post("/api/pulse/create/{room_id}")
async def create_pulse(room_id: str):
    r = redis.from_url(redis_url, decode_responses=True)
    pulse_id = str(uuid.uuid4())
    await r.setex(f"pulse:{pulse_id}", 60, room_id)
    await r.close()
    return {"pulse_id": pulse_id, "expires_in": 60}

@app.post("/api/pulse/join")
async def join_by_pulse(request: PulseRequest):
    r = redis.from_url(redis_url, decode_responses=True)
    room_id = await r.get(f"pulse:{request.pulse_id}")
    if not room_id:
        raise HTTPException(status_code=404, detail="Pulse not found or expired.")
    await r.delete(f"pulse:{request.pulse_id}")
    await r.close()
    return {"room_id": room_id}

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data, room_id, websocket) # Отправляем всем, кроме себя
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)