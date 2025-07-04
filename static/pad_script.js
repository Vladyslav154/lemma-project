document.addEventListener('DOMContentLoaded', () => {
    // ... (все переменные остаются теми же) ...
    const passwordOverlay = document.getElementById('password-overlay');
    // ... и так далее

    let ws;
    let encryptionKey = '';
    let peerConnection;
    let localStream;
    const servers = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

    // --- Функции ---
    const encryptMessage = (msg, key) => CryptoJS.AES.encrypt(JSON.stringify(msg), key).toString();
    const decryptMessage = (encMsg, key) => CryptoJS.AES.decrypt(encMsg, key).toString(CryptoJS.enc.Utf8);
    const sendMessageToServer = (type, payload) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type, payload }));
        }
    };

    const displayChatMessage = (messageData) => {
        const msgDiv = document.createElement('div');
        msgDiv.textContent = messageData.message;
        messages.appendChild(msgDiv);
        messages.scrollTop = messages.scrollHeight;
        if (messageData.ttl > 0) {
            setTimeout(() => {
                msgDiv.style.transition = 'opacity 0.5s';
                msgDiv.style.opacity = '0';
                setTimeout(() => msgDiv.remove(), 500);
            }, messageData.ttl * 1000);
        }
    };

    const handleIncomingChatMessage = (payload) => {
        try {
            const decryptedPayload = decryptMessage(payload, encryptionKey);
            const data = JSON.parse(decryptedPayload);
            if (data.message) {
                displayChatMessage(data);
            }
        } catch (e) { console.error("Ошибка дешифровки:", e); }
    };
    
    // ... (остальной код, включая WebRTC, остается таким же, но я привожу его полностью для надежности) ...
    const handleWebRTCSignal = async (signal) => {
        try {
            if (!peerConnection && (signal.type === 'answer' || signal.type === 'ice-candidate')) return;
            if (!peerConnection) await setupPeerConnection();

            if (signal.type === 'offer') {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(signal.offer));
                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);
                sendMessageToServer('webrtc', { type: 'answer', answer: answer });
            } else if (signal.type === 'answer') {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(signal.answer));
            } else if (signal.type === 'ice-candidate') {
                await peerConnection.addIceCandidate(new RTCIceCandidate(signal.candidate));
            }
        } catch (e) { console.error("Ошибка WebRTC:", e); }
    };

    const setupPeerConnection = async () => {
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        peerConnection = new RTCPeerConnection(servers);
        localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));
        peerConnection.ontrack = event => { remoteAudio.srcObject = event.streams[0]; };
        peerConnection.onicecandidate = event => {
            if (event.candidate) sendMessageToServer('webrtc', { type: 'ice-candidate', candidate: event.candidate });
        };
        callBtn.disabled = true;
        callBtn.textContent = "Звонок активен...";
    };

    const initializeWebSocket = () => {
        let boardId = window.location.pathname.split('/pad/')[1] || Math.random().toString(36).substring(2, 12);
        if (!window.location.pathname.includes(boardId)) {
            window.history.replaceState({}, document.title, `/pad/${boardId}`);
        }
        
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/${boardId}`;
        ws = new WebSocket(wsUrl);
        ws.onopen = () => { status.textContent = `Вы в защищенной комнате: ${boardId}`; };
        ws.onclose = () => { status.textContent = 'Соединение потеряно.'; };
        ws.onmessage = async (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'chat') handleIncomingChatMessage(data.payload);
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
            sendMessageToServer('chat', encryptedPayload);
            // ИСПРАВЛЕНИЕ: Мгновенно показываем собственное сообщение
            displayChatMessage(messageData);
            input.value = '';
        }
    });

    callBtn.addEventListener('click', async () => {
        await setupPeerConnection();
        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);
        sendMessageToServer('webrtc', { type: 'offer', offer: offer });
    });
});