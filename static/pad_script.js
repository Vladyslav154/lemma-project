document.addEventListener('DOMContentLoaded', () => {
    const passwordOverlay = document.getElementById('password-overlay');
    const passwordForm = document.getElementById('password-form');
    const passwordInput = document.getElementById('password-input');
    const chatWrapper = document.getElementById('chat-wrapper');

    const status = document.getElementById('status');
    const messages = document.getElementById('messages');
    const form = document.getElementById('form');
    const input = document.getElementById('message-input');

    let ws;

    // Шаг 1: Обработка ввода пароля
    passwordForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const password = passwordInput.value;
        if (!password) {
            alert('Пожалуйста, введите пароль.');
            return;
        }

        // В будущем здесь будет генерация ключа шифрования из пароля.
        // const encryptionKey = await generateKeyFromPassword(password);

        // Скрываем окно пароля и показываем чат
        passwordOverlay.style.display = 'none';
        chatWrapper.style.display = 'flex';
        
        // Шаг 2: Инициализация WebSocket ПОСЛЕ ввода пароля
        initializeWebSocket();
    });

    // Шаг 3: Функция инициализации чата
    function initializeWebSocket() {
        let boardId = window.location.pathname.split('/pad/')[1];
        if (!boardId || boardId.trim() === '') {
            boardId = Math.random().toString(36).substring(2, 12);
            window.history.replaceState({}, document.title, `/pad/${boardId}`);
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/${boardId}`;
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            status.textContent = `Вы в анонимной комнате: ${boardId}`;
        };

        ws.onmessage = (event) => {
            // В будущем здесь будет дешифровка сообщения
            // const decryptedMessage = await decryptMessage(event.data, encryptionKey);
            const messageDiv = document.createElement('div');
            messageDiv.textContent = event.data; // Пока показываем как есть
            messages.appendChild(messageDiv);
            messages.scrollTop = messages.scrollHeight;
        };

        ws.onclose = () => {
            status.textContent = 'Соединение потеряно.';
        };

        form.addEventListener('submit', (event) => {
            event.preventDefault();
            if (input.value && ws && ws.readyState === WebSocket.OPEN) {
                // В будущем здесь будет шифрование сообщения
                // const encryptedMessage = await encryptMessage(input.value, encryptionKey);
                ws.send(input.value); // Пока отправляем как есть
                input.value = '';
            }
        });
    }
});