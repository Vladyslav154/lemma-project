import os
import uuid
import json
import asyncio
from typing import Dict, List, Optional
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
from fastapi.concurrency import run_in_threadpool
import time

# --- Конфигурация ---
load_dotenv()
app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Словарь переводов ---
translations = {
    "ru": { "app_title": "Lepko", "app_subtitle": "Простые инструменты для простых задач.", "upgrade_link": "Получить Pro", "activate_key": "Активировать ключ", "drop_title": "Файлообменник", "drop_description": "Быстрая и анонимная передача файлов.", "pad_title": "Чат-комнаты", "pad_description": "Создайте анонимную комнату для общения.", "home_button": "Домой", "drop_page_title": "Приватная передача файлов", "drop_page_subtitle": "Ссылка сработает один раз и исчезнет через 15 минут.", "drop_zone_text": "Перетащите файл сюда или кликните для выбора", "uploading_text": "Загрузка...", "ready_text": "Ваш файл готов к отправке!", "copy_button": "Копировать", "one_time_link_text": "Эта ссылка сработает только один раз.", "send_another_file": "Отправить еще один файл", "pad_page_title": "Анонимный чат", "pad_room_subtitle": "Вы в комнате:", "pad_disclaimer": "Сообщения исчезают. Ничего не сохраняется.", "message_placeholder": "Введите сообщение...", "password_set_title": "Установить пароль для комнаты", "password_set_subtitle": "Первый вошедший задает пароль.", "password_enter_title": "Комната защищена", "password_enter_subtitle": "Введите пароль для входа.", "password_placeholder": "Введите пароль...", "enter_button": "Войти", "copied_button": "Скопировано!", "pro_title": "Lepko Pro", "pro_subtitle": "Получите доступ к расширенным функциям и поддержите проект.", "pro_features_title": "Что вы получаете:", "pro_feature_1": "Увеличенный лимит на размер файла до 100 МБ", "pro_feature_2": "Более долгое время жизни ссылок (24 часа)", "pro_feature_3": "Приоритетная поддержка", "pro_feature_4": "Ваша поддержка помогает нам оставаться независимыми", "how_to_get_pro": "Как получить Pro:", "payment_info": "Для сохранения полной анонимности мы принимаем оплату только в криптовалюте Monero (XMR).", "payment_step_1": "Отправьте нужную сумму на этот адрес:", "payment_step_2": "После отправки, вставьте ID вашей транзакции в поле ниже для верификации.", "txn_id_placeholder": "ID транзакции (TxID)", "verify_payment_button": "Проверить платеж", "monthly_plan": "Месяц", "yearly_plan": "Год"},
    "en": { "app_title": "Lepko", "app_subtitle": "Simple tools for simple tasks.", "upgrade_link": "Get Pro", "activate_key": "Activate Key", "drop_title": "File Drop", "drop_description": "Fast and anonymous file transfer.", "pad_title": "Chat Rooms", "pad_description": "Create an anonymous room for communication.", "home_button": "Home", "drop_page_title": "Private File Transfer", "drop_page_subtitle": "The link will work once and expire in 15 minutes.", "drop_zone_text": "Drag and drop a file here or click to select", "uploading_text": "Uploading...", "ready_text": "Your file is ready to be sent!", "copy_button": "Copy", "one_time_link_text": "This link will only work once.", "send_another_file": "Send another file", "pad_page_title": "Anonymous Chat", "pad_room_subtitle": "You are in room:", "pad_disclaimer": "Messages disappear. Nothing is saved.", "message_placeholder": "Enter a message...", "password_set_title": "Set a password for the room", "password_set_subtitle": "The first user to enter sets the password.", "password_enter_title": "Room is Protected", "password_enter_subtitle": "Enter the password to join.", "password_placeholder": "Enter password...", "enter_button": "Enter", "copied_button": "Copied!", "pro_title": "Lepko Pro", "pro_subtitle": "Get access to advanced features and support the project.", "pro_features_title": "What you get:", "pro_feature_1": "Increased file size limit up to 100 MB", "pro_feature_2": "Longer link lifetime (24 hours)", "pro_feature_3": "Priority support", "pro_feature_4": "Your support helps us stay independent", "how_to_get_pro": "How to get Pro:", "payment_info": "To maintain full anonymity, we only accept payments in Monero (XMR).", "payment_step_1": "Send the required amount to this address:", "payment_step_2": "After sending, paste your transaction ID in the field below for verification.", "txn_id_placeholder": "Transaction ID (TxID)", "verify_payment_button": "Verify Payment", "monthly_plan": "Month", "yearly_plan": "Year"}
}

# --- Настройки и хранилища ---
MAX_FILE_SIZE = 25 * 1024 * 1024
PRO_MAX_FILE_SIZE = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".docx", ".zip", ".rar"}
file_links = {}
trial_keys = {}

# --- Менеджер подключений чата ---
class ConnectionManager:
    # ... (код ConnectionManager без изменений)
    pass
manager = ConnectionManager()

# --- Эндпоинты ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, lang: str = Query("ru", regex="ru|en")):
    def t(key: str) -> str: return translations.get(lang, {}).get(key, key)
    return templates.TemplateResponse("index.html", {"request": request, "t": t, "lang": lang})

# ... (все остальные эндпоинты, включая WebSocket)