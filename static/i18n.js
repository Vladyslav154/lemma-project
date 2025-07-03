// static/i18n.js
async function setLanguage(lang) {
    // Загружаем файл-словарь для выбранного языка
    const response = await fetch(`/static/lang/${lang}.json`);
    const translations = await response.json();

    // Находим все элементы, которые нужно перевести
    document.querySelectorAll('[data-i18n-key]').forEach(element => {
        const key = element.getAttribute('data-i18n-key');
        if (translations[key]) {
            element.textContent = translations[key];
        }
    });
}

// Определяем язык браузера пользователя
const userLang = navigator.language.split('-')[0];

// По умолчанию загружаем английский, если язык браузера не русский
const defaultLang = (userLang === 'ru') ? 'ru' : 'en';

// Устанавливаем язык при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    setLanguage(defaultLang);
});