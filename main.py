import asyncio
import os
import uuid
import datetime
import html
import json
from pathlib import Path
from typing import Optional

import aiofiles
import redis
from fastapi import FastAPI, Request, UploadFile, WebSocket, WebSocketDisconnect, HTTPException, status, Depends, Form, Header
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# --- Настройка ---
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL, decode_responses=True)

UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
board_connections = {}

# --- Настройки безопасности ---
STANDARD_MAX_FILE_SIZE = 100 * 1024 * 1024
PREMIUM_MAX_FILE_SIZE = 1024 * 1024 * 1024
ALLOWED_FILE_TYPES = ["image/", "video/", "audio/", "application/pdf", "application/zip", "text/plain", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]

# --- Маршруты HTML ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request): return templates.TemplateResponse("home.html", {"request": request})

@app.get("/drop", response_class=HTMLResponse)
async def read_drop(request: Request): return templates.TemplateResponse("drop.html", {"request": request})

@app.get("/pad/{board_id:path}", response_class=HTMLResponse)
async def read_pad_board(request: Request, board_id: str): return templates.TemplateResponse("pad.html", {"request": request, "board_id": board_id})

@app.get("/upgrade", response_class=HTMLResponse)
async def read_upgrade(request: Request): return templates.TemplateResponse("upgrade.html", {"request": request})

@app.get("/activate", response_class=HTMLResponse)
async def read_activate(request: Request): return templates.TemplateResponse("activate.html", {"request": request})

# --- API ---
@app.get("/stats")
def get_stats():
    keys_generated = r.get("lepko:stats:keys_generated") or 0
    files_transferred = r.get("lepko:stats:files_transferred") or 0
    return {"keys_generated": int(keys_generated), "files_transferred": int(files_transferred)}

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile, authorization: Optional[str] = Header(None)):
    is_premium = False
    if authorization and authorization.startswith("Bearer "):
        key = authorization.split("Bearer ")[1]
        if r.get(f"lepko:key:{key}"): is_premium = True
    max_size = PREMIUM_MAX_FILE_SIZE if is_premium else STANDARD_MAX_FILE_SIZE
    if file.size > max_size:
        limit_mb = int(max_size / 1024 / 1024)
        raise HTTPException(status_code=413, detail=f"Файл слишком большой. Ваш лимит: {limit_mb} МБ.")
    is_allowed = any(file.content_type.startswith(allowed_type) for allowed_type in ALLOWED_FILE_TYPES)
    if not is_allowed: raise HTTPException(status_code=400, detail="Недопустимый тип файла.")
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / file.filename
    async with aiofiles.open(file_path, "wb") as f:
        while content := await file.read(1024 * 1024): await f.write(content)
    r.set(f"lepko:drop:{file_id}", str(file_path), ex=3600)
    r.incr("lepko:stats:files_transferred")
    return {"file_id": file_id}

@app.get("/file/{file_id}")
async def get_file(file_id: str):
    file_path_str = r.get(f"lepko:drop:{file_id}")
    if not file_path_str: return HTMLResponse(content="<h1>Файл не найден или срок его действия истек.</h1>", status_code=404)
    file_path = Path(file_path_str)
    if not file_path.exists(): return HTMLResponse(content="<h1>Ошибка: Файл не найден на диске сервера.</h1>", status_code=404)
    r.delete(f"lepko:drop:{file_id}")
    tasks = BackgroundTasks()
    tasks.add_task(os.remove, file_path)
    return FileResponse(path=file_path, filename=Path(file_path_str).name, background=tasks)

@app.websocket("/ws/{board_id}")
async def websocket_endpoint(websocket: WebSocket, board_id: str):
    await websocket.accept()
    if board_id not in board_connections: board_connections[board_id] = []
    board_connections[board_id].append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            for connection in board_connections[board_id]:
                await connection.send_text(data)
    except WebSocketDisconnect:
        board_connections[board_id].remove(websocket)

@app.post('/keys/generate', status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def generate_payment_link(request: Request, plan_type: str = Form(...)):
    if not COINBASE_API_KEY:
        raise HTTPException(status_code=503, detail="Платежная система не настроена на сервере.")
    if plan_type not in ["monthly", "yearly"]:
        raise HTTPException(status_code=400, detail="Неверный тип плана.")
    name = "Lepko Premium (1 месяц)" if plan_type == "monthly" else "Lepko Premium (1 год)"
    amount = "14.00" if plan_type == "monthly" else "110.00"
    try:
        client = Client(api_key=COINBASE_API_KEY)
        charge = client.charge.create(
            name=name,
            description=f'Анонимный ключ доступа к Lepko Premium.',
            local_price={'amount': amount, 'currency': 'USD'},
            pricing_type='fixed_price',
            redirect_url=f"https://{request.url.hostname}/",
            cancel_url=f"https://{request.url.hostname}/upgrade",
        )
        r.incr("lepko:stats:keys_generated")
        return {"payment_url": charge.hosted_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Coinbase: {e}")

@app.post('/keys/generate_trial', status_code=status.HTTP_201_CREATED)
@limiter.limit("1/day")
def generate_trial_key(request: Request):
    new_key_string = f"LEPKO-TRIAL-{str(uuid.uuid4()).upper()}"
    expires_in_seconds = 14 * 24 * 60 * 60
    r.set(f"lepko:key:{new_key_string}", "trial", ex=expires_in_seconds)
    r.incr("lepko:stats:keys_generated")
    return {"access_key": new_key_string}

@app.get("/keys/check/{key_string}")
def check_key(key_string: str):
    plan_type = r.get(f"lepko:key:{key_string}")
    if not plan_type: raise HTTPException(status_code=404, detail="Ключ не найден или истек.")
    return {"status": "active", "plan": plan_type}