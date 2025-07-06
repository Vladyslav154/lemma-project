import os
import uuid
import json
import asyncio
from typing import Dict, List
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, WebSocket, WebSocketDisconnect, Path
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
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
    "ru": { "app_title": "Lepko", "app_subtitle": "Простые инструменты для простых задач.", "upgrade_link": "Получить Pro", "activate_key": "Активировать ключ", "drop_description": "Быстрая и анонимная передача файлов.", "pad_description": "Общий блокнот между вашими устройствами." },
    "en": { "app_title": "Lepko", "app_subtitle": "Simple tools for simple tasks.", "upgrade_link": "Get Pro", "activate_key": "Activate Key", "drop_description": "Fast and anonymous file transfer.", "pad_description": "A shared notepad between your devices." }
}

# --- Настройки безопасности для файлов ---
MAX_FILE_SIZE = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".docx", ".zip", ".rar"}

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
            await websocket.send_text(json.dumps({"type": "auth_success", "message": "Пароль установлен."}))
            return True
        elif self.room_passwords.get(room_id) == password:
            self.active_connections[room_id].append(websocket)
            await websocket.send_text(json.dumps({"type": "auth_success", "message": "Доступ разрешен."}))
            return True
        else:
            await websocket.send_text(json.dumps({"type": "auth_fail", "message": "Неверный пароль."}))
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
@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/ru")

@app.get("/{lang}", response_class=HTMLResponse)
async def read_root(request: Request, lang: str = Path(regex="ru|en")):
    def t(key: str) -> str: return translations.get(lang