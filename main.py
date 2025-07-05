import os
import uuid
import redis
import cloudinary
import cloudinary.uploader
import json
from typing import Dict, List
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# --- Define the absolute path to the project's root directory ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Translation Dictionary ---
translations = {
    "app_title": "Lepko",
    "app_subtitle": "Простые инструменты для простых задач.",
    "upgrade_link": "Получить Pro",
    "activate_key": "Активировать ключ",
    "drop_description": "Быстрая и анонимная передача файлов.",
    "pad_description": "Общий блокнот между вашими устройствами.",
    "keys_issued": "Ключей выдано",
    "files_transferred": "Файлов передано"
}

# --- Configuration ---
load_dotenv()
app = FastAPI()

# Configure Cloudinary
cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

# Connect to Redis
redis_url = os.getenv("REDIS_URL")
if not redis_url:
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
else:
    r = redis.from_url(redis_url, decode_responses=True)

# Mount static files and templates with absolute paths
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# --- WebSocket Connection Manager for Chat Rooms ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections and websocket in self.active_connections[room_id]:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, message: str, room_id: str):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_text(message)

manager = ConnectionManager()


# --- API Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    def t(key: str) -> str:
        return translations.get(key, key)
    return templates.TemplateResponse("index.html", {"request": request, "t": t})

@app.get("/drop", response_class=HTMLResponse)
async def drop_page(request: Request):
    def t(key: str) -> str:
        return translations.get(key, key)
    return templates.TemplateResponse("drop.html", {"request": request, "t": t})

@app.get("/pad")
async def pad_redirect():
    """Redirects to a new unique pad room."""
    room_id = str(uuid.uuid4().hex[:8])
    return RedirectResponse(url=f"/pad/{room_id}")

@app.get("/pad/{room_id}", response_class=HTMLResponse)
async def pad_room(request: Request, room_id: str):
    """Serves the specific shared notepad room."""
    def t(key: str) -> str:
        return translations.get(key, key)
    return templates.TemplateResponse("pad_room.html", {"request": request, "room_id": room_id, "t": t})

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    upload_result = cloudinary.uploader.upload(file.file, resource_type="auto")
    file_url = upload_result.get("secure_url")
    link_id = str(uuid.uuid4().hex[:10])
    r.setex(link_id, 900, file_url)
    base_url = str(request.base_url)
    one_time_link = f"{base_url}file/{link_id}"
    return {"download_link": one_time_link}

@app.get("/file/{link_id}")
async def get_file_redirect(link_id: str):
    file_url = r.get(link_id)
    if not file_url:
        raise HTTPException(status_code=404, detail="Link is invalid, has been used, or has expired.")
    r.delete(link_id)
    return RedirectResponse(url=file_url)

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket, room_id)
    try:
        while True:
            # Принимаем данные, которые теперь должны быть в формате JSON
            data = await websocket.receive_text()
            # Просто пересылаем их всем в комнате
            await manager.broadcast(data, room_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)