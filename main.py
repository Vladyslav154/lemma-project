import asyncio
import os
import uuid
from pathlib import Path

import aiofiles
import redis
from fastapi import FastAPI, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, BackgroundTask # Убедитесь, что BackgroundTask здесь
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- Настройка ---
app = FastAPI()
r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Хранилище для чат-комнат ---
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

# --- API для "Drop" ---
@app.post("/upload")
async def upload_file(file: UploadFile):
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"

    # Стриминг файла на диск по частям для экономии памяти
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while content := await file.read(1024 * 1024):  # Читаем по 1MB
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

    # Правильное удаление файла в фоновом режиме
    task = BackgroundTask(os.remove, file_path)
    return FileResponse(path=file_path, filename=file_path.name, background=task)

# --- API для "Pad" ---
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