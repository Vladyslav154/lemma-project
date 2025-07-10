import os
import uuid
import json
import shutil
from pathlib import Path
from fastapi import FastAPI, Request, Form, HTTPException, WebSocket, Query, UploadFile, File, Header
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import redis.asyncio as redis
from typing import Dict, Callable, Optional

# --- Инициализация ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Настройки ---
UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# --- Логика перевода ---
def load_translations() -> Dict[str, Dict[str, str]]:
    translations = {}
    for lang in ['en', 'ru']:
        try:
            with open(f'lang/{lang}.json', 'r', encoding='utf-8') as f:
                translations[lang] = json.load(f)
        except FileNotFoundError:
            print(f"WARNING: Translation file lang/{lang}.json not found.")
            translations[lang] = {}
    return translations

translations_data = load_translations()

def get_translator(lang: str = 'ru') -> Callable[[str], str]:
    default_lang_data = translations_data.get('ru', {})
    lang_data = translations_data.get(lang, default_lang_data)
    def translator(key: str) -> str:
        return lang_data.get(key, key)
    return translator

# Подключение к Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost")
redis_client = redis.from_url(redis_url, decode_responses=True)


# --- Класс для управления WebSocket ---
class ConnectionManager:
    # ... (код ConnectionManager остается без изменений) ...
    def __init__(self):
        self.active_connections: Dict[str, list[WebSocket]] = {}
    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections: self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections: self.active_connections[room_id].remove(websocket)
    async def broadcast(self, message: str, room_id: str):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_text(message)

manager = ConnectionManager()


# --- Маршруты HTTP ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, lang: str = 'ru'):
    t = get_translator(lang)
    return templates.TemplateResponse("index.html", {"request": request, "t": t, "lang": lang})

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, lang: str = 'ru'):
    t = get_translator(lang)
    return templates.TemplateResponse("about.html", {"request": request, "t": t, "lang": lang})

@app.get("/drop", response_class=HTMLResponse)
async def drop_page(request: Request, lang: str = 'ru'):
    t = get_translator(lang)
    return templates.TemplateResponse("drop.html", {"request": request, "t": t, "lang": lang})

# --- ИЗМЕНЕННЫЙ МАРШРУТ ДЛЯ ЗАГРУЗКИ ФАЙЛА ---
@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), lang: str = 'ru', authorization: Optional[str] = Header(None)):
    file_id = str(uuid.uuid4().hex)
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    await redis_client.set(f"file:{file_id}", str(file_path), ex=3600) # Файл хранится час
    
    # Собираем полную ссылку для скачивания
    download_link = str(request.url_for('download_file', file_id=file_id))
    
    # Возвращаем JSON, как этого ожидает ваш JavaScript
    return JSONResponse(content={"download_link": download_link})

@app.get("/download/{file_id}")
async def download_file(request: Request, file_id: str):
    file_path_str = await redis_client.get(f"file:{file_id}")
    
    if not file_path_str:
        # Для API лучше вернуть JSON-ошибку, но для прямого скачивания можно и так
        raise HTTPException(status_code=404, detail="File not found or has expired.")
        
    file_path = Path(file_path_str)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found on server.")

    # Удаляем запись из Redis, чтобы ссылка стала одноразовой
    await redis_client.delete(f"file:{file_id}")
    
    return FileResponse(path=file_path, filename=file_path.name.split('_', 1)[1], media_type='application/octet-stream')


@app.post("/create_pad")
async def create_pad(request: Request, lang: str = 'ru'):
    room_id = str(uuid.uuid4().hex)[:8]
    await redis_client.set(f"pad:{room_id}:exists", "1", ex=3600)
    return RedirectResponse(url=f"/pad/{room_id}?lang={lang}", status_code=303)

@app.get("/pad/{room_id}", response_class=HTMLResponse)
async def get_pad(request: Request, room_id: str, lang: str = 'ru'):
    if not await redis_client.exists(f"pad:{room_id}:exists"):
        raise HTTPException(status_code=404, detail="Room not found or has expired.")
    t = get_translator(lang)
    return templates.TemplateResponse("pad_room.html", {"request": request, "room_id": room_id, "t": t, "lang": lang})


# --- Маршрут WebSocket ---
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    if not await redis_client.exists(f"pad:{room_id}:exists"):
        await websocket.close(code=1008)
        return
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data, room_id)
    except Exception:
        manager.disconnect(websocket, room_id)
