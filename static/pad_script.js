// static/pad_script.js
document.addEventListener('DOMContentLoaded', () => {
    const editor = document.getElementById('editor');
    const status = document.getElementById('status');

    // --- БЛОК ГЕНЕРАЦИИ УНИКАЛЬНОГО URL ---
    // Получаем ID доски из URL.
    let boardId = window.location.pathname.split('/')[2];

    // Если ID в URL нет, создаем новый и обновляем адресную строку.
    if (!boardId || boardId.trim() === '') {
        boardId = Math.random().toString(36).substring(2, 12);
        window.history.replaceState({}, document.title, `/pad/${boardId}`);
    }
    // --- КОНЕЦ БЛОКА ---

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/${boardId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        status.textContent = `Подключено к доске: ${boardId}`;
        status.style.color = '#28a745';
    };

    ws.onmessage = (event) => {
        if (editor.value !== event.data) {
            editor.value = event.data;
        }
    };

    ws.onclose = () => {
        status.textContent = 'Соединение потеряно. Попробуйте обновить страницу.';
        status.style.color = '#dc3545';
    };

    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }

    const debouncedSend = debounce((text) => {
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(text);
        }
    }, 300);

    editor.addEventListener('input', () => {
        debouncedSend(editor.value);
    });
});