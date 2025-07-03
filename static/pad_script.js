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
    let encryptionKey = ''; // Здесь будет храниться ключ шифрования

    // --- Функции шифрования ---
    function encryptMessage(message, key) {
        return CryptoJS.AES.encrypt(message, key).toString();
    }

    function decryptMessage(encryptedMessage, key) {
        const bytes = CryptoJS.AES.decrypt(encryptedMessage, key);
        return bytes.toString(CryptoJS.enc.Utf8);
    }

    // --- Логика приложения ---
    passwordForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const password = passwordInput.value;
        if (!password) {
            alert('Пожалуйста, введите пароль.');
            return;
        }
        encryptionKey = password; // Используем пароль как ключ шифрования
        passwordOverlay.style.display = 'none';
        chatWrapper.style.display = 'flex';
        initializeWebSocket();
    });

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
            status.textContent = `Вы в защищенной комнате: ${boardId}`;
        };

        ws.onmessage = (event) => {
            try {
                const decryptedMessage = decryptMessage(event.data, encryptionKey);
                if (decryptedMessage) {
                    const messageDiv = document.createElement('div');
                    messageDiv.textContent = decryptedMessage;
                    messages.appendChild(messageDiv);
                    messages.scrollTop = messages.scrollHeight;
                }
            } catch (e) {
                console.error("Failed to decrypt message. Wrong password?", e);
            }
        };

        ws.onclose = () => {
            status.textContent = 'Соединение потеряно.';
        };

        form.addEventListener('submit', (event) => {
            event.preventDefault();
            if (input.value && ws && ws.readyState === WebSocket.OPEN) {
                const encryptedMessage = encryptMessage(input.value, encryptionKey);
                ws.send(encryptedMessage);
                input.value = '';
            }
        });
    }
});