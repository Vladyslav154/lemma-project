document.addEventListener('DOMContentLoaded', () => {
    // --- Элементы DOM ---
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

    // --- Переменные состояния ---
    let ws;
    let encryptionKey = '';
    
    // --- Инициализация ---
    // Генерируем URL СРАЗУ при загрузке страницы
    let boardId = window.location.pathname.split('/pad/')[1];
    if (!boardId || boardId.trim() === '') {
        boardId = Math.random().toString(36).substring(2, 12);
        window.history.replaceState({}, document.title, `/pad/${boardId}`);
    }

    // --- Функции ---
    const encryptMessage = (msg, key) => CryptoJS.AES.encrypt(JSON.stringify(msg), key).toString();
    const decryptMessage = (encMsg, key) => CryptoJS.AES.decrypt(encMsg, key).toString(CryptoJS.enc.Utf8);

    const handleIncomingMessage = (encryptedPayload) => {
        try {
            const decryptedPayload = decryptMessage(encryptedPayload, encryptionKey);
            const data = JSON.parse(decryptedPayload);
            if (data.message) {
                const msgDiv = document.createElement('div');
                msgDiv.textContent = data.message;
                messages.appendChild(msgDiv);
                messages.scrollTop = messages.scrollHeight;
                if (data.ttl > 0) {
                    setTimeout(() => {
                        msgDiv.style.transition = 'opacity 0.5s';
                        msgDiv.style.opacity = '0';
                        setTimeout(() => msgDiv.remove(), 500);
                    }, data.ttl * 1000);
                }
            }
        } catch (e) { console.error("Ошибка дешифровки:", e); }
    };

    const initializeWebSocket = () => {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/${boardId}`;
        ws = new WebSocket(wsUrl);
        ws.onopen = () => { status.textContent = `Вы в защищенной комнате: ${boardId}`; };
        ws.onclose = () => { status.textContent = 'Соединение потеряно.'; };
        ws.onmessage = (event) => handleIncomingMessage(event.data);
    };

    // --- Обработчики событий ---
    passwordForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const password = passwordInput.value;
        if (!password) { alert('Пожалуйста, введите пароль.'); return; }
        encryptionKey = password;
        passwordOverlay.style.display = 'none';
        chatWrapper.style.display = 'flex';
        const accessKey = localStorage.getItem('lepko_access_key');
        if (accessKey) premiumOptions.style.display = 'block';
        initializeWebSocket();
    });

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        if (input.value && ws && ws.readyState === WebSocket.OPEN) {
            const messageData = { message: input.value, ttl: parseInt(ttlSelect.value, 10) };
            const encryptedPayload = encryptMessage(messageData, encryptionKey);
            ws.send(encryptedPayload);
            input.value = '';
        }
    });
});