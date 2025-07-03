import asyncio
import os
import uuid
from pathlib import Path  # <--- ЭТА СТРОКА БЫЛА ПРОПУЩЕНА
import datetime

import aiofiles
import redis
from fastapi import FastAPI, Request, UploadFile, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- Настройка ---
app = FastAPI()

# Подключаемся к Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL, decode_responses=True)

# Остальные настройки
UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
board_connections = {}


# --- Маршруты для страниц (HTML) ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/drop", response_class=HTMLResponse)
async def read_drop(request: Request):
    return templates.TemplateResponse("drop.html", {"request": request})

@app.get("/pad/{board_id:path}", response_class=HTMLResponse)
async def read_pad_board(request: Request, board_id: str):
    return templates.TemplateResponse("pad.html", {"request": request, "board_id": board_id})

@app.get("/upgrade", response_class=HTMLResponse)
async def read_upgrade(request: Request):
    return templates.TemplateResponse("upgrade.html", {"request": request})


# --- API для "Drop" ---
@app.post("/upload")
async def upload_file(file: UploadFile):
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while content := await file.read(1024 * 1024):
                await f.write(content)
    except Exception:
        return {"error": "Failed to save file on server."}, 500
    r.set(f"lepko:drop:{file_id}", str(file_path), ex=3600)
    return {"file_id": file_id}

@app.get("/file/{file_id}")
async def get_file(file_id: str):
    file_path_str = r.get(f"lepko:drop:{file_id}")
    if not file_path_str:
        return HTMLResponse(content="<h1>Файл не найден или срок его действия истек.</h1>", status_code=404)
    file_path = Path(file_path_str)
    if not file_path.exists():
        return HTMLResponse(content="<h1>Ошибка: Файл не найден на диске сервера.</h1>", status_code=404)
    r.delete(f"lepko:drop:{file_id}")
    tasks = BackgroundTasks()
    tasks.add_task(os.remove, file_path)
    return FileResponse(path=file_path, filename=file_path.name, background=tasks)


# --- API для "Pad" (анонимный чат) ---
@app.websocket("/ws/{board_id}")
async def websocket_endpoint(websocket: WebSocket, board_id: str):
    await websocket.accept()
    if board_id not in board_connections:
        board_connections[board_id] = []
    board_connections[board_id].append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            for connection in board_connections[board_id]:
                await connection.send_text(data)
    except WebSocketDisconnect:
        board_connections[board_id].remove(websocket)


# --- API для генерации ключей доступа (работает с Redis) ---
@app.post('/keys/generate', status_code=status.HTTP_201_CREATED)
def generate_key(plan_type: str):
    if plan_type not in ["monthly", "yearly"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный тип плана.")
    
    new_key_string = f"LEPKO-{plan_type.upper()}-{str(uuid.uuid4()).upper()}"
    
    now = datetime.datetime.utcnow()
    if plan_type == "monthly":
        expires_in_seconds = 30 * 24 * 60 * 60
    else: # yearly
        expires_in_seconds = 365 * 24 * 60 * 60

    r.set(f"lepko:key:{new_key_string}", plan_type, ex=expires_in_seconds)
    
    expires_at = now + datetime.timedelta(seconds=expires_in_seconds)
    return {"access_key": new_key_string, "expires_at": expires_at.isoformat()}

