import os
import json
import secrets
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from werkzeug.utils import secure_filename
from coinbase_commerce.client import Client

# --- 1. Базовая настройка ---
app = FastAPI()

# Подключаем middleware для сессий (чтобы помнить язык)
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(16))

# Подключаем папки для статики (css) и шаблонов (html)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Папка для временных загрузок
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- 2. Настройка Coinbase Commerce ---
# ВАЖНО: Вставьте ваш реальный API ключ в переменные окружения на Render
COINBASE_API_KEY = os.getenv('COINBASE_API_KEY', 'ВАШ_КЛЮЧ_ПО_УМОЛЧАНИЮ')
client = Client(api_key=COINBASE_API_KEY)

# --- 3. Логика перевода ---
TRANSLATIONS = {}
# Возвращаем все языки, которые мы добавляли
LANGUAGES = {'en': 'EN', 'ru': 'RU', 'de': 'DE', 'cs': 'CS', 'uk': 'UK'}

def load_translations():
    lang_dir = os.path.join('static', 'lang')
    for lang_code in LANGUAGES:
        file_path = os.path.join(lang_dir, f'{lang_code}.json')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                TRANSLATIONS[lang_code] = json.load(f)

load_translations() # Загружаем переводы при старте

# --- 4. Главная функция для рендеринга шаблонов ---
def render(template_name: str, request: Request, context: dict = {}):
    lang_code = request.query_params.get('lang', request.session.get('lang', 'en'))
    if lang_code in LANGUAGES:
        request.session['lang'] = lang_code

    def t(key: str):
        return TRANSLATIONS.get(lang_code, {}).get(key, key)

    full_context = {"request": request, "t": t, "LANGUAGES": LANGUAGES, "current_lang": lang_code, **context}
    return templates.TemplateResponse(template_name, full_context)

# --- 5. Маршруты (Routes) ---

@app.get("/", response_class=HTMLResponse)
async def route_root(request: Request):
    return render("home.html", request)

# --- Drop (Загрузка файлов) ---
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
    t = render("", request).context['t']
    return HTMLResponse(f'<h1>{t("drop_success_title")}</h1><p>{t("drop_success_message")} <a href="{download_link}">{download_link}</a></p><a href="/drop">{t("drop_success_back_button")}</a>')

@app.get("/uploads/{filename}")
async def route_get_upload(filename: str):
    return FileResponse(path=os.path.join(UPLOAD_FOLDER, filename), filename=filename)

# --- Pad (Защищенные заметки) ---
@app.get("/pad", response_class=HTMLResponse)
async def route_get_pad(request: Request):
    return render("pad.html", request)

@app.post("/pad/create")
async def route_create_pad_room(request: Request, password: str = Form(...)):
    # Генерируем уникальный ID для комнаты
    room_id = secrets.token_urlsafe(8)
    # В реальном приложении пароль нужно было бы сохранить (например, в Redis)
    # Сейчас мы просто создаем ссылку
    return RedirectResponse(url=f"/pad/{room_id}?pass={password}", status_code=303)

@app.get("/pad/{room_id}", response_class=HTMLResponse)
async def route_get_pad_room(request: Request, room_id: str):
    # Просто отображаем страницу комнаты, пароль можно будет использовать на фронтенде для шифрования
    return render("pad_room.html", request, {"room_id": room_id})


# --- Upgrade (Премиум и оплата) ---
@app.get("/upgrade", response_class=HTMLResponse)
async def route_get_upgrade(request: Request):
    return render("upgrade.html", request)

@app.post("/create_charge", response_class=HTMLResponse)
async def route_create_charge(request: Request):
    t = render("", request).context['t']
    charge_info = {
        'name': t('premium_charge_name'),
        'description': t('premium_charge_description'),
        'local_price': {
            'amount': '10.00', # Цена
            'currency': 'USD'  # Валюта
        },
        'pricing_type': 'fixed_price',
        'redirect_url': str(request.base_url) + 'payment_success', # Страница после успешной оплаты
        'cancel_url': str(request.base_url) + 'upgrade' # Страница при отмене
    }
    charge = client.charge.create(**charge_info)
    return RedirectResponse(charge.hosted_url, status_code=303)

@app.get("/payment_success", response_class=HTMLResponse)
async def route_payment_success(request: Request):
    t = render("", request).context['t']
    return HTMLResponse(f"<h1>{t('payment_success_title')}</h1><p>{t('payment_success_message')}</p>")