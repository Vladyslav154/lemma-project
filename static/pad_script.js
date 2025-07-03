document.addEventListener('DOMContentLoaded', () => {
    const passwordOverlay = document.getElementById('password-overlay');
    const passwordForm = document.getElementById('password-form');
    const passwordInput = document.getElementById('password-input');
    const chatWrapper = document.getElementById('chat-wrapper');
    const premiumOptions = document.getElementById('premium-options');
    const ttlSelect = document.getElementById('ttl-select');

    const status = document.getElementById('status');
    const messages = document.getElementById('messages');
    const form = document.getElementById('form');
    const input = document.getElementById('message-input');

    let ws;
    let encryptionKey = '';

    function encryptMessage(message, key) { return CryptoJS.AES.encrypt(JSON.stringify(message), key).toString(); }
    function decryptMessage(encryptedMessage, key) { const bytes = CryptoJS.AES.decrypt(encryptedMessage, key); return bytes.toString(CryptoJS.enc.Utf8); }

    passwordForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const password = passwordInput.value;
        if (!password) { alert('Пожалуйста, введите пароль.'); return; }
        encryptionKey = password;
        passwordOverlay.style.display = 'none';
        chatWrapper.style.display = 'flex';
        
        const accessKey = localStorage.getItem('lepko_access_key');
        if (accessKey) {
            premiumOptions.style.display = 'block';
        }

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

        ws.onopen = () => { status.textContent = `Вы в защищенной комнате: ${boardId}`; };
        ws.onclose = () => { status.textContent = 'Соединение потеряно.'; };

        ws.onmessage = (event) => {
            try {
                // --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
                // Шаг 1: Сначала РАСШИФРОВЫВАЕМ полученный пакет.
                const decryptedPayloadString = decryptMessage(event.data, encryptionKey);
                
                // Шаг 2: Теперь, когда у нас есть чистый JSON-текст, ПАРСИМ его.
                const data = JSON.parse(decryptedPayloadString);
                
                if (data.message) {
                    const messageDiv = document.createElement('div');
                    messageDiv.textContent = data.message;
                    messages.appendChild(messageDiv);
                    messages.scrollTop = messages.scrollHeight;

                    if (data.ttl > 0) {
                        setTimeout(() => {
                            messageDiv.style.transition = 'opacity 0.5s';
                            messageDiv.style.opacity = '0';
                            setTimeout(() => messageDiv.remove(), 500);
                        }, data.ttl * 1000);
                    }
                }
            } catch (e) { console.error("Ошибка дешифровки или парсинга:", e); }
        };

        form.addEventListener('submit', (event) => {
            event.preventDefault();
            if (input.value && ws && ws.readyState === WebSocket.OPEN) {
                const messageData = {
                    message: input.value,
                    ttl: parseInt(ttlSelect.value, 10)
                };
                
                const encryptedPayload = encryptMessage(messageData, encryptionKey);
                ws.send(encryptedPayload);
                input.value = '';
            }
        });
    }
});