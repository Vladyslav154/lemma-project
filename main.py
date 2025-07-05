import os
import uuid
import redis
import cloudinary
import cloudinary.uploader
import json
import asyncio
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
    r = redis.Redis(host='localhost', port=6379, db=0) # decode_responses=False for pubsub
else:
    r = redis.from_url(redis_url) # decode_responses=False for pubsub

# Mount static files and templates with absolute paths
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


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
    # Using a different Redis instance for simple key-value stores
    r_kv = redis.from_url(redis_url, decode_responses=True)
    r_kv.setex(link_id, 900, file_url)
    base_url = str(request.base_url)
    one_time_link = f"{base_url}file/{link_id}"
    return {"download_link": one_time_link}

@app.get("/file/{link_id}")
async def get_file_redirect(link_id: str):
    r_kv = redis.from_url(redis_url, decode_responses=True)
    file_url = r_kv.get(link_id)
    if not file_url:
        raise HTTPException(status_code=404, detail="Link is invalid, has been used, or has expired.")
    r_kv.delete(link_id)
    return RedirectResponse(url=file_url)

# --- WebSocket Logic with Redis Pub/Sub ---
async def redis_pubsub_reader(websocket: WebSocket, room_id: str):
    """Слушает сообщения из Redis и отправляет их клиенту через WebSocket."""
    pubsub = r.pubsub()
    await pubsub.subscribe(f"chat:{room_id}")
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                await websocket.send_text(message['data'].decode('utf-8'))
            await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        await pubsub.unsubscribe(f"chat:{room_id}")

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """Принимает сообщения от клиента и публикует их в Redis."""
    await websocket.accept()
    
    # Запускаем задачу, которая слушает Redis
    pubsub_task = asyncio.create_task(redis_pubsub_reader(websocket, room_id))
    
    try:
        while True:
            # Получаем сообщение от клиента
            data = await websocket.receive_text()
            # Публикуем его в канал Redis для этой комнаты
            await r.publish(f"chat:{room_id}", data)
    except WebSocketDisconnect:
        # Если клиент отключается, отменяем задачу-слушателя
        pubsub_task.cancel()
        await pubsub_task