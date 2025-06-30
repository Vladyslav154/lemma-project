import os
import uuid
import asyncio
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.websockets import WebSocket, WebSocketDisconnect

# --- 1. Начальная настройка приложения ---
app = FastAPI(title="Lemma Tools")

# Подключаем папки для статики и шаблонов
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Простое хранилище в памяти вместо Redis для локального запуска
# Мы создадим его при старте приложения
# app.state.file_db = {} 
# app.state.board_content = {} 

# --- 2. Логика для "Одноразового Файла" (Drop) ---
UPLOAD_DIR = "temp_uploads" # Используем локальную папку для простоты
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())[:8]
    file_path = os.path.join(UPLOAD_DIR, file_id)
    
    try:
        with open(file_path, "wb") as buffer:
            contents = await file.read()
            buffer.write(contents)
        
        app.state.file_db[file_id] = {'path': file_path, 'name': file.filename}
        asyncio.create_task(delete_file_after_delay(file_id, 900)) # 15 минут
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")
        
    download_link = f"/file/{file_id}"
    return {"download_link": download_link}

@app.get("/file/{file_id}")
async def download_file(file_id: str):
    if file_id in app.state.file_db:
        file_info = app.state.file_db.pop(file_id)
        file_path = file_info['path']
        if os.path.exists(file_path):
            return FileResponse(path=file_path, filename=file_info['name'], media_type='application/octet-stream')
    raise HTTPException(status_code=404, detail="File not found or has already been downloaded.")

async def delete_file_after_delay(file_id: str, delay: int):
    await asyncio.sleep(delay)
    if file_id in app.state.file_db:
        file_info = app.state.file_db.pop(file_id)
        if os.path.exists(file_info['path']):
            os.remove(file_info['path'])
        print(f"File {file_id} expired and was deleted.")

# --- 3. Логика для "Общего Блокнота" (Pad) ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
    async def connect(self, websocket: WebSocket, board_id: str):
        await websocket.accept()
        if board_id not in self.active_connections:
            self.active_connections[board_id] = []
        self.active_connections[board_id].append(websocket)
        if board_id in app.state.board_content:
            await websocket.send_text(app.state.board_content[board_id])
    def disconnect(self, websocket: WebSocket, board_id: str):
        self.active_connections[board_id].remove(websocket)
    async def broadcast(self, message: str, board_id: str):
        app.state.board_content[board_id] = message
        for connection in self.active_connections[board_id]:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/{board_id}")
async def websocket_endpoint(websocket: WebSocket, board_id: str):
    await manager.connect(websocket, board_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data, board_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, board_id)

# --- 4. Маршруты для HTML-страниц и запуск ---
@app.on_event("startup")
def on_startup():
    app.state.file_db = {}
    app.state.board_content = {}

@app.get("/", response_class=HTMLResponse)
async def read_home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/drop", response_class=HTMLResponse)
async def read_drop(request: Request):
    return templates.TemplateResponse("drop.html", {"request": request})

@app.get("/pad")
async def read_pad_random():
    random_id = str(uuid.uuid4())[:6]
    return RedirectResponse(url=f"/pad/{random_id}")

@app.get("/pad/{board_id}", response_class=HTMLResponse)
async def read_pad_with_id(request: Request, board_id: str):
    return templates.TemplateResponse("pad.html", {"request": request, "board_id": board_id})
    
@app.get("/qr", response_class=HTMLResponse)
async def read_qr(request: Request):
    return templates.TemplateResponse("qr.html", {"request": request})
    # -- Project version 2 --
