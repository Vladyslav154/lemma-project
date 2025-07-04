import os
import json
from flask import request, session

class Translator:
    def __init__(self, app):
        self.app = app
        self.translations = {}
        # Словарь с доступными языками и их отображаемыми названиями
        self.LANGUAGES = {
            'en': 'EN',
            'ru': 'RU',
            'de': 'DE',
            'cs': 'CS',
            'uk': 'UK'
        }
        self.load_translations()
        self.init_hooks()

    def load_translations(self):
        # Загружаем все json файлы из папки lang
        lang_dir = os.path.join(self.app.static_folder, 'lang')
        for lang_code in self.LANGUAGES:
            file_path = os.path.join(lang_dir, f'{lang_code}.json')
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)

    def get_lang(self):
        # Получаем язык из сессии или из запроса, по умолчанию 'en'
        lang = session.get('lang')
        if 'lang' in request.args:
            lang_arg = request.args.get('lang')
            if lang_arg in self.LANGUAGES:
                lang = lang_arg
                session['lang'] = lang
        
        # Если язык так и не определен, ставим 'en'
        if lang not in self.LANGUAGES:
            lang = 'en'
            session['lang'] = lang
            
        return lang

    def translate(self, key, **kwargs):
        lang = self.get_lang()
        # Получаем строку по ключу, с возможностью отката на английский
        text = self.translations.get(lang, {}).get(key, self.translations.get('en', {}).get(key, key))
        # Форматируем строку, если переданы доп. аргументы
        return text.format(**kwargs)

    def init_hooks(self):
        # Эта функция делает 't' и 'LANGUAGES' доступными во всех шаблонах
        @self.app.context_processor
        def inject_translator():
            return {
                't': self.translate,
                'LANGUAGES': self.LANGUAGES,
                'current_lang': self.get_lang()
            }