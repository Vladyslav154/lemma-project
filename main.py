import os
import uuid
import json
import asyncio
from typing import Dict, List
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
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

translations = { "app_title": "Lepko", "app_subtitle": "Простые инструменты для простых задач.", "upgrade_link": "Получить Pro", "activate_key": "Активировать ключ", "drop_description": "Быстрая и анонимная передача файлов.", "pad_description": "Общий блокнот между вашими устройствами."}

# --- Менеджер подключений с логикой паролей ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.room_passwords: Dict[str, str] = {} # Словарь для хранения паролей

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        # Проверяем, есть ли уже пароль для этой комнаты
        if room_id in self.room_passwords:
            await websocket.send_text(json.dumps({"type": "auth_required", "action": "enter"}))
        else:
            await websocket.send_text(json.dumps({"type": "auth_required", "action": "set"}))

    async def auth_and_join(self, websocket: WebSocket, room_id: str, password: str):
        # Если комнаты и пароля нет, устанавливаем его
        if room_id not in self.room_passwords:
            self.room_passwords[room_id] = password
            if room_id not in self.active_connections:
                self.active_connections[room_id] = []
            self.active_connections[room_id].append(websocket)
            await websocket.send_text(json.dumps({"type": "auth_success", "message": "Пароль установлен."}))
            return True
        # Если пароль есть и он верный
        elif self.room_passwords.get(room_id) == password:
            self.active_connections[room_id].append(websocket)
            await websocket.send_text(json.dumps({"type": "auth_success", "message": "Доступ разрешен."}))
            return True
        # Если пароль неверный
        else:
            await websocket.send_text(json.dumps({"type": "auth_fail", "message": "Неверный пароль."}))
            return False

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections and websocket in self.active_connections[room_id]:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]: # Если в комнате никого не осталось
                del self.active_connections[room_id]
                if room_id in self.room_passwords:
                    del self.room_passwords[room_id] # Удаляем пароль

    async def broadcast(self, message: str, room_id: str, sender: WebSocket):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                if connection != sender:
                    await connection.send_text(message)

manager = ConnectionManager()

# --- Эндпоинты ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    def t(key: str) -> str: return translations.get(key, key)
    return templates.TemplateResponse("index.html", {"request": request, "t": t})

@app.get("/drop", response_class=HTMLResponse)
async def drop_page(request: Request):
    def t(key: str) -> str: return translations.get(key, key)
    return templates.TemplateResponse("drop.html", {"request": request, "t": t})

@app.get("/pad")
async def pad_redirect():
    room_id = str(uuid.uuid4().hex[:8])
    return RedirectResponse(url=f"/pad/{room_id}")

@app.get("/pad/{room_id}", response_class=HTMLResponse)
async def pad_room(request: Request, room_id: str):
    def t(key: str) -> str: return translations.get(key, key)
    return templates.TemplateResponse("pad_room.html", {"request": request, "room_id": room_id, "t": t})

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    upload_result = cloudinary.uploader.upload(file.file, resource_type="auto")
    file_url = upload_result.get("secure_url")
    link_id = str(uuid.uuid4().hex[:10])
    r_kv = redis.from_url(redis_url, decode_responses=True)
    await r_kv.setex(link_id, 900, file_url)
    await r_kv.close()
    return {"download_link": one_time_link}

@app.get("/file/{link_id}")
async def get_file_redirect(link_id: str):
    r_kv = redis.from_url(redis_url, decode_responses=True)
    file_url = await r_kv.get(link_id)
    if not file_url: raise HTTPException(status_code=404, detail="Link is invalid, has been used, or has expired.")
    await r_kv.delete(link_id)
    await r_kv.close()
    return RedirectResponse(url=file_url)

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket, room_id)
    
    try:
        # --- Аутентификация ---
        auth_data_str = await websocket.receive_text()
        auth_data = json.loads(auth_data_str)
        if auth_data.get("type") == "auth":
            password = auth_data.get("password")
            is_authed = await manager.auth_and_join(websocket, room_id, password)
            if not is_authed:
                return # Закрываем соединение, если пароль неверный
        else: # Если первое сообщение не для авторизации
            await websocket.close()
            return

        # --- Основной цикл чата ---
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data, room_id, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)