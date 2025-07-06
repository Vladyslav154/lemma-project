import os
import uuid
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
import redis.asyncio as redis

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

# Get Redis URL from environment variables
redis_url = os.getenv("REDIS_URL")
if not redis_url:
    raise ValueError("REDIS_URL is not set in the environment")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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
    room_id = str(uuid.uuid4().hex[:8])
    return RedirectResponse(url=f"/pad/{room_id}")

@app.get("/pad/{room_id}", response_class=HTMLResponse)
async def pad_room(request: Request, room_id: str):
    def t(key: str) -> str:
        return translations.get(key, key)
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
    if not file_url:
        raise HTTPException(status_code=404, detail="Link is invalid, has been used, or has expired.")
    await r_kv.delete(link_id)
    await r_kv.close()
    return RedirectResponse(url=file_url)

# --- WebSocket Logic with Passwords ---
async def redis_reader(channel: redis.client.PubSub, websocket: WebSocket):
    async for message in channel.listen():
        if message['type'] == 'message':
            await websocket.send_text(message['data'].decode('utf-8'))

async def websocket_reader(websocket: WebSocket, channel: str):
    r_pub = redis.from_url(redis_url)
    async for message in websocket.iter_text():
        await r_pub.publish(channel, message)
    await r_pub.close()

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    r = redis.from_url(redis_url, decode_responses=True)
    channel = f"chat:{room_id}"
    password_key = f"password:{room_id}"

    # --- Логика пароля ---
    room_password = await r.get(password_key)
    try:
        auth_data_str = await websocket.receive_text()
        auth_data = json.loads(auth_data_str)
        password = auth_data.get("password")

        if not room_password: # Если пароля для комнаты нет, этот пользователь его устанавливает
            await r.setex(password_key, 3600, password) # Пароль живет 1 час
            await websocket.send_text(json.dumps({"type": "auth_success", "message": "Пароль установлен."}))
        elif password != room_password: # Если пароль есть, но он неверный
            await websocket.send_text(json.dumps({"type": "auth_fail", "message": "Неверный пароль."}))
            await websocket.close()
            await r.close()
            return
        else: # Если пароль верный
            await websocket.send_text(json.dumps({"type": "auth_success", "message": "Доступ разрешен."}))

    except (WebSocketDisconnect, json.JSONDecodeError):
        await websocket.close()
        await r.close()
        return

    # --- Основная логика чата после успешной авторизации ---
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)

    consumer_task = asyncio.create_task(redis_reader(pubsub, websocket))
    producer_task = asyncio.create_task(websocket_reader(websocket, channel))
    
    done, pending = await asyncio.wait(
        [consumer_task, producer_task], return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
    
    await pubsub.close()
    await r.close()