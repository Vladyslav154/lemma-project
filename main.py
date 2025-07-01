import asyncio
import os
import uuid
from pathlib import Path
from typing import Dict, List

import aiofiles
from fastapi import FastAPI, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- Базовая настройка ---
app = FastAPI()

# Папка для временного хранения загруженных файлов
UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Подключение шаблонов и статических файлов
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Хранилища в памяти (вместо Redis для простоты) ---

# Для хранения информации о файлах в Drop
file_database: Dict[str, Path] = {}

# Для хранения текста досок в Pad
board_database: Dict[str, str] = {}
# Для хранения активных подключений к доскам
board_connections: Dict[str, List[WebSocket]] = {}


# --- Маршруты для страниц (HTML) ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/drop", response_class=HTMLResponse)
async def read_drop(request: Request):
    return templates.TemplateResponse("drop.html", {"request": request})

@app.get("/pad", response_class=HTMLResponse)
async def read_pad_root(request: Request):
    # Если зашли на /pad без ID, показываем страницу
    return templates.TemplateResponse("pad.html", {"request": request})

@app.get("/pad/{board_id}", response_class=HTMLResponse)
async def read_pad_board(request: Request, board_id: str):
    # Если зашли на /pad с ID, также показываем страницу
    return templates.TemplateResponse("pad.html", {"request": request, "board_id": board_id})


# --- API для инструмента "Drop" ---

@app.post("/upload")
async def upload_file(file: UploadFile):
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    file_database[file_id] = file_path
    return {"file_id": file_id}

@app.get("/file/{file_id}")
async def get_file(file_id: str):
    file_path = file_database.get(file_id)
    if not file_path or not file_path.exists():
        return {"error": "File not found or has been downloaded"}, 404

    # Удаляем запись о файле, чтобы его нельзя было скачать снова
    del file_database[file_id]

    # Возвращаем файл для скачивания и удаляем его с диска после отправки
    return FileResponse(path=file_path, filename=file_path.name, background=asyncio.create_task(os.remove(file_path)))


# --- API для инструмента "Pad" (WebSocket) ---

@app.websocket("/ws/{board_id}")
async def websocket_endpoint(websocket: WebSocket, board_id: str):
    await websocket.accept()
    
    # Создаем список подключений для доски, если его нет
    if board_id not in board_connections:
        board_connections[board_id] = []
    board_connections[board_id].append(websocket)

    # При первом подключении отправляем текущий текст доски
    current_text = board_database.get(board_id, "")
    await websocket.send_text(current_text)

    try:
        while True:
            # Получаем новый текст от одного из клиентов
            data = await websocket.receive_text()
            # Сохраняем его в нашей базе
            board_database[board_id] = data
            # Рассылаем этот текст всем остальным подключенным клиентам
            for connection in board_connections[board_id]:
                if connection != websocket:
                    await connection.send_text(data)
    except WebSocketDisconnect:
        # Убираем клиента из списка при отключении
        board_connections[board_id].remove(websocket)