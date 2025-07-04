import os
import json
from fastapi import FastAPI, Request, File, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from werkzeug.utils import secure_filename
import secrets

# --- 1. Настройка приложения ---
app = FastAPI()

# Добавляем "сессии" для запоминания языка. Нужен пакет starlette.
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(16))

# Подключаем папки для статики (css) и шаблонов (html)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Папка для загружаемых файлов
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- 2. Логика перевода (встроена прямо сюда) ---
TRANSLATIONS = {}
LANGUAGES = {'en': 'EN', 'ru': 'RU'}

def load_translations():
    lang_dir = os.path.join('static', 'lang')
    for lang_code in LANGUAGES:
        file_path = os.path.join(lang_dir, f'{lang_code}.json')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                TRANSLATIONS[lang_code] = json.load(f)

load_translations() # Загружаем переводы при старте сервера

# --- 3. Главная функция для рендеринга шаблонов с переводом ---
def render(template_name: str, request: Request, context: dict = {}):
    # Определяем язык для текущего запроса
    lang_code = request.query_params.get('lang')
    if lang_code in LANGUAGES:
        request.session['lang'] = lang_code
    else:
        lang_code = request.session.get('lang', 'en')

    # Создаем функцию `t` для перевода внутри шаблонов
    def t(key: str):
        return TRANSLATIONS.get(lang_code, {}).get(key, key)

    # Собираем полный контекст для шаблона
    full_context = {
        "request": request,
        "t": t,
        "LANGUAGES": LANGUAGES,
        "current_lang": lang_code,
        **context
    }
    return templates.TemplateResponse(template_name, full_context)

# --- 4. Маршруты (Routes) ---

@app.get("/", response_class=HTMLResponse)
async def route_root(request: Request):
    return render("home.html", request)

@app.get("/drop", response_class=HTMLResponse)
async def route_get_drop(request: Request):
    return render("drop.html", request)

@app.post("/drop", response_class=HTMLResponse)
async def route_post_drop(request: Request, file: UploadFile = File(...)):
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    download_link = str(request.base_url) + 'uploads/' + filename
    # Предполагаем, что есть шаблон drop_success.html
    return render("drop_success.html", request, {"link": download_link})

@app.get("/uploads/{filename}")
async def route_get_upload(filename: str):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=filename)
    return HTMLResponse("File not found", status_code=404)

@app.get("/pad", response_class=HTMLResponse)
async def route_get_pad(request: Request):
    return render("pad.html", request)

@app.get("/pad/{room_name}", response_class=HTMLResponse)
async def route_pad_room(request: Request, room_name: str):
    return render("pad_room.html", request, {"room_name": room_name})

@app.get("/upgrade", response_class=HTMLResponse)
async def route_get_upgrade(request: Request):
    return render("upgrade.html", request)