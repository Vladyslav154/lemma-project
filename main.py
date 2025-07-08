import os
import uuid
import json
import asyncio
from typing import Dict, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, WebSocket, WebSocketDisconnect, Query, Header
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
    "ru": { "app_title": "Lepko", "app_subtitle": "Простые инструменты для простых задач.", "upgrade_link": "Получить Pro", "activate_key": "Активировать ключ", "drop_title": "Файлообменник", "drop_description": "Быстрая и анонимная передача файлов.", "pad_title": "Чат-комнаты", "pad_description": "Создайте анонимную комнату для общения.", "home_button": "Домой"},
    "en": { "app_title": "Lepko", "app_subtitle": "Simple tools for simple tasks.", "upgrade_link": "Get Pro", "activate_key": "Activate Key", "drop_title": "File Drop", "drop_description": "Fast and anonymous file transfer.", "pad_title": "Chat Rooms", "pad_description": "Create an anonymous room for communication.", "home_button": "Home"}
}

# --- Менеджер подключений чата ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.room_passwords: Dict[str, str] = {}
    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id in self.room_passwords: await websocket.send_text(json.dumps({"type": "auth_required", "action": "enter"}))
        else: await websocket.send_text(json.dumps({"type": "auth_required", "action": "set"}))
    async def auth_and_join(self, websocket: WebSocket, room_id: str, password: str):
        if room_id not in self.room_passwords:
            self.room_passwords[room_id] = password
            if room_id not in self.active_connections: self.active_connections[room_id] = []
            self.active_connections[room_id].append(websocket)
            await websocket.send_text(json.dumps({"type": "auth_success"}))
            return True
        elif self.room_passwords.get(room_id) == password:
            self.active_connections[room_id].append(websocket)
            await websocket.send_text(json.dumps({"type": "auth_success"}))
            return True
        else:
            await websocket.send_text(json.dumps({"type": "auth_fail"}))
            return False
    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections and websocket in self.active_connections[room_id]:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
                if room_id in self.room_passwords: del self.room_passwords[room_id]
    async def broadcast(self, message: str, room_id: str, sender: WebSocket):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                if connection != sender: await connection.send_text(message)
manager = ConnectionManager()

# --- Эндпоинты ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, lang: str = Query("ru", regex="ru|en")):
    def t(key: str) -> str: return translations.get(lang, {}).get(key, key)
    return templates.TemplateResponse("index.html", {"request": request, "t": t, "lang": lang})

@app.get("/pad")
async def pad_redirect(lang: str = Query("ru", regex="ru|en")):
    room_id = str(uuid.uuid4().hex[:8])
    return RedirectResponse(url=f"/pad/{room_id}?lang={lang}")

@app.get("/pad/{room_id}", response_class=HTMLResponse)
async def pad_room(request: Request, room_id: str, lang: str = Query("ru", regex="ru|en")):
    def t(key: str) -> str: return translations.get(lang, {}).get(key, key)
    return templates.TemplateResponse("pad_room.html", {"request": request, "room_id": room_id, "t": t, "lang": lang})

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket, room_id)
    try:
        auth_data_str = await websocket.receive_text()
        auth_data = json.loads(auth_data_str)
        if auth_data.get("type") == "auth":
            password = auth_data.get("password")
            is_authed = await manager.auth_and_join(websocket, room_id, password)
            if not is_authed: return
        else:
            await websocket.close()
            return
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data, room_id, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)