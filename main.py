import os
import uuid
import json
import asyncio
from typing import Dict, List
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, WebSocket, WebSocketDisconnect, Query
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
    "ru": {
        "app_title": "Lepko", "app_subtitle": "Простые инструменты для простых задач.", "upgrade_link": "Получить Pro", "activate_key": "Активировать ключ", "drop_title": "Drop", "drop_description": "Быстрая и анонимная передача файлов.", "pad_title": "Pad", "pad_description": "Общий блокнот между вашими устройствами.", "keys_issued": "Ключей выдано", "files_transferred": "Файлов передано", "drop_page_title": "Приватная передача файлов", "drop_page_subtitle": "Ссылка сработает один раз и исчезнет через 15 минут.", "drop_zone_text": "Перетащите файл сюда или кликните для выбора", "uploading_text": "Загрузка...", "ready_text": "Ваш файл готов к отправке!", "copy_button": "Копировать", "one_time_link_text": "Эта ссылка сработает только один раз.", "send_another_file": "Отправить еще один файл", "pad_page_title": "Анонимный чат", "pad_room_subtitle": "Вы в комнате:", "pad_disclaimer": "Сообщения исчезают. Ничего не сохраняется.", "message_placeholder": "Введите сообщение...", "password_set_title": "Установить пароль для комнаты", "password_set_subtitle": "Первый вошедший задает пароль.", "password_enter_title": "Комната защищена", "password_enter_subtitle": "Введите пароль для входа.", "password_placeholder": "Введите пароль...", "enter_button": "Войти", "copied_button": "Скопировано!", "home_button": "Домой"
    },
    "en": {
        "app_title": "Lepko", "app_subtitle": "Simple tools for simple tasks.", "upgrade_link": "Get Pro", "activate_key": "Activate Key", "drop_title": "Drop", "drop_description": "Fast and anonymous file transfer.", "pad_title": "Pad", "pad_description": "A shared notepad between your devices.", "keys_issued": "Keys issued", "files_transferred": "Files transferred", "drop_page_title": "Private File Transfer", "drop_page_subtitle": "The link will work once and expire in 15 minutes.", "drop_zone_text": "Drag and drop a file here or click to select", "uploading_text": "Uploading...", "ready_text": "Your file is ready to be sent!", "copy_button": "Copy", "one_time_link_text": "This link will only work once.", "send_another_file": "Send another file", "pad_page_title": "Anonymous Chat", "pad_room_subtitle": "You are in room:", "pad_disclaimer": "Messages disappear. Nothing is saved.", "message_placeholder": "Enter a message...", "password_set_title": "Set a password for the room", "password_set_subtitle": "The first user to enter sets the password.", "password_enter_title": "Room is Protected", "password_enter_subtitle": "Enter the password to join.", "password_placeholder": "Enter password...", "enter_button": "Enter", "copied_button": "Copied!", "home_button": "Home"
    }
}

# --- Настройки безопасности для файлов ---
MAX_FILE_SIZE = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".docx", ".zip", ".rar"}

# --- Менеджер подключений чата ---
class ConnectionManager:
    # ... (код ConnectionManager остается без изменений)
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
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, lang: str = Query("ru", regex="ru|en")):
    def t(key: str) -> str: return translations.get(lang, {}).get(key, key)
    return templates.TemplateResponse("index.html", {"request": request, "t": t, "lang": lang})

# ИСПРАВЛЕНО: Добавлена функция перевода t
@app.get("/drop", response_class=HTMLResponse)
async def drop_page(request: Request, lang: str = Query("ru", regex="ru|en")):
    def t(key: str) -> str: return translations.get(lang, {}).get(key, key)
    return templates.TemplateResponse("drop.html", {"request": request, "t": t, "lang": lang})

@app.get("/pad")
async def pad_redirect(lang: str = Query("ru", regex="ru|en")):
    room_id = str(uuid.uuid4().hex[:8])
    return RedirectResponse(url=f"/pad/{room_id}?lang={lang}")

# ИСПРАВЛЕНО: Добавлена функция перевода t
@app.get("/pad/{room_id}", response_class=HTMLResponse)
async def pad_room(request: Request, room_id: str, lang: str = Query("ru", regex="ru|en")):
    def t(key: str) -> str: return translations.get(lang, {}).get(key, key)
    return templates.TemplateResponse("pad_room.html", {"request": request, "room_id": room_id, "t": t, "lang": lang})

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Недопустимый тип файла. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}")
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Файл слишком большой. Максимальный размер: {MAX_FILE_SIZE // 1024 // 1024}MB")
    upload_result = cloudinary.uploader.upload(contents, resource_type="auto")
    file_url = upload_result.get("secure_url")
    link_id = str(uuid.uuid4().hex[:10])
    r_kv = redis.from_url(redis_url, decode_responses=True)
    await r_kv.setex(link_id, 900, file_url)
    await r_kv.close()
    base_url = str(request.base_url).rstrip('/')
    one_time_link = f"{base_url}/file/{link_id}"
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