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
    return {
        "keys_generated": int(keys_generated),
        "files_transferred": int(files_transferred)
    }

@app.post("/upload")
async def upload_file(request: Request