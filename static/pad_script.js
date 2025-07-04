document.addEventListener('DOMContentLoaded', () => {
    // --- Переменные ---
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
    const callBtn = document.getElementById('call-btn');
    const remoteAudio = document.getElementById('remote-audio');

    let ws;
    let encryptionKey = '';
    let peerConnection;
    let localStream;
    const servers = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

    // --- Инициализация при загрузке ---
    // Сразу генерируем URL, если его нет
    let boardId = window.location.pathname.split('/pad/')[1] || Math.random().toString(36).substring(2, 12);
    if (!window.location.pathname.includes(boardId)) {
        window.history.replaceState({}, document.title, `/pad/${boardId}`);
    }

    // --- Функции ---
    const encryptMessage = (msg, key) => CryptoJS.AES.encrypt(JSON.stringify(msg), key).toString();
    const decryptMessage = (encMsg, key) => CryptoJS.AES.decrypt(encMsg, key).toString(CryptoJS.enc.Utf8);

    const sendMessage = (type, payload) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type, payload }));
        }
    };

    const setupPeerConnection = async () => {
        if (peerConnection) return;
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        peerConnection = new RTCPeerConnection(servers);
        localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));
        peerConnection.ontrack = event => { remoteAudio.srcObject = event.streams[0]; };
        peerConnection.onicecandidate = event => {
            if (event.candidate) sendMessage('webrtc', { type: 'ice-candidate', candidate: event.candidate });
        };
        callBtn.disabled = true;
        callBtn.textContent = "Звонок активен...";
    };

    const handleChatMessage = (payload) => {
        try {
            const decryptedPayload = decryptMessage(payload, encryptionKey);
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

    const handleWebRTCSignal = async (signal) => {
        try {
            if (signal.type === 'offer') {
                await setupPeerConnection();
                await peerConnection.setRemoteDescription(new RTCSessionDescription(signal.offer));
                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);
                sendMessage('webrtc', { type: 'answer', answer: answer });
            } else if (signal.type === 'answer') {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(signal.answer));
            } else if (signal.type === 'ice-candidate') {
                if (peerConnection) await peerConnection.addIceCandidate(new RTCIceCandidate(signal.candidate));
            }
        } catch (e) { console.error("Ошибка WebRTC:", e); }
    };

    const initializeWebSocket = () => {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/${boardId}`;
        ws = new WebSocket(wsUrl);
        ws.onopen = () => { status.textContent = `Вы в защищенной комнате: ${boardId}`; };
        ws.onclose = () => { status.textContent = 'Соединение потеряно.'; };
        ws.onmessage = async (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'chat') handleChatMessage(data.payload);
            else if (data.type === 'webrtc') await handleWebRTCSignal(data.payload);
        };
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
        if (input.value) {
            const messageData = { message: input.value, ttl: parseInt(ttlSelect.value, 10) };
            const encryptedPayload = encryptMessage(messageData, encryptionKey);
            sendMessage('chat', encryptedPayload);
            input.value = '';
        }
    });

    callBtn.addEventListener('click', async () => {
        await setupPeerConnection();
        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);
        sendMessage('webrtc', { type: 'offer', offer: offer });
    });
});