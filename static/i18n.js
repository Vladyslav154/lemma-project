// static/i18n.js
async function setLanguage(lang) {
    // Сохраняем выбор пользователя в память браузера
    localStorage.setItem('lepko_language', lang);

    const response = await fetch(`/static/lang/${lang}.json`);
    const translations = await response.json();

    document.querySelectorAll('[data-i18n-key]').forEach(element => {
        const key = element.getAttribute('data-i18n-key');
        if (translations[key]) {
            element.textContent = translations[key];
        }
    });
}

// Определяем, какой язык загружать
function getInitialLanguage() {
    // Сначала ищем выбор пользователя в памяти
    const savedLang = localStorage.getItem('lepko_language');
    if (savedLang) {
        return savedLang;
    }
    // Если его нет, определяем по языку браузера
    const userLang = navigator.language.split('-')[0];
    return (userLang === 'ru') ? 'ru' : 'en';
}

// Устанавливаем язык при первой загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    setLanguage(getInitialLanguage());
});