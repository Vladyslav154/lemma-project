import os
import uuid
import redis
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# --- УДАЛЕНА ЛОГИКА С АБСОЛЮТНЫМИ ПУТЯМИ ---

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

# --- ИЗМЕНЕНО: Простое монтирование ---
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

@app.get("/pad", response_class=HTMLResponse)
async def pad_page(request: Request):
    def t(key: str) -> str:
        return translations.get(key, key)
    return templates.TemplateResponse("pad.html", {"request": request, "t": t})

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