document.addEventListener('DOMContentLoaded', () => {
    const status = document.getElementById('status');
    const messages = document.getElementById('messages');
    const form = document.getElementById('form');
    const input = document.getElementById('message-input');

    // Получаем ID комнаты из URL. Если его нет, создаем новый.
    let boardId = window.location.pathname.split('/pad/')[1];
    if (!boardId || boardId.trim() === '') {
        boardId = Math.random().toString(36).substring(2, 12);
        window.history.replaceState({}, document.title, `/pad/${boardId}`);
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/${boardId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        status.textContent = `Вы в анонимной комнате: ${boardId}`;
    };

    ws.onmessage = (event) => {
        const messageDiv = document.createElement('div');
        messageDiv.textContent = event.data;
        messages.appendChild(messageDiv);
        // Автопрокрутка вниз при новом сообщении
        messages.scrollTop = messages.scrollHeight;
    };

    ws.onclose = () => {
        status.textContent = 'Соединение потеряно.';
    };

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        if (input.value && ws.readyState === WebSocket.OPEN) {
            ws.send(input.value);
            input.value = ''; // Очищаем поле ввода
        }
    });
});