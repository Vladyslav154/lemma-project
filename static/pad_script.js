document.addEventListener('DOMContentLoaded', () => {
    // --- Переменные для всего скрипта ---
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

    // --- Конфигурация для WebRTC ---
    const servers = {
        iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' },
        ],
    };

    // --- Функции шифрования (без изменений) ---
    function encryptMessage(message, key) { return CryptoJS.AES.encrypt(JSON.stringify(message), key).toString(); }
    function decryptMessage(encryptedMessage, key) { const bytes = CryptoJS.AES.decrypt(encryptedMessage, key); return bytes.toString(CryptoJS.enc.Utf8); }

    // --- Основная логика ---
    passwordForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const password = passwordInput.value;
        if (!password) { alert('Пожалуйста, введите пароль.'); return; }
        encryptionKey = password;
        passwordOverlay.style.display = 'none';
        chatWrapper.style.display = 'flex';
        
        const accessKey = localStorage.getItem('lepko_access_key');
        if (accessKey) { premiumOptions.style.display = 'block'; }

        initializeWebSocket();
    });

    // --- WebRTC Логика ---
    callBtn.addEventListener('click', async () => {
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        peerConnection = new RTCPeerConnection(servers);

        localStream.getTracks().forEach(track => {
            peerConnection.addTrack(track, localStream);
        });

        peerConnection.ontrack = (event) => {
            remoteAudio.srcObject = event.streams[0];
        };

        peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                ws.send(JSON.stringify({ type: 'ice-candidate', candidate: event.candidate }));
            }
        };

        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);
        ws.send(JSON.stringify({ type: 'offer', offer: offer }));
        
        callBtn.disabled = true;
        callBtn.textContent = "Звонок активен...";
    });

    // --- Инициализация WebSocket ---
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

        ws.onmessage = async (event) => {
            // Проверяем, это сообщение для чата или для WebRTC
            try {
                const signal = JSON.parse(event.data);

                // --- Обработка сигналов WebRTC ---
                if (signal.type === 'offer') {
                    if (!peerConnection) {
                         // Если мы получаем предложение, инициализируем соединение
                        localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
                        peerConnection = new RTCPeerConnection(servers);

                        localStream.getTracks().forEach(track => {
                            peerConnection.addTrack(track, localStream);
                        });

                        peerConnection.ontrack = (event) => {
                            remoteAudio.srcObject = event.streams[0];
                        };

                        peerConnection.onicecandidate = (event) => {
                            if (event.candidate) {
                                ws.send(JSON.stringify({ type: 'ice-candidate', candidate: event.candidate }));
                            }
                        };
                    }
                    
                    await peerConnection.setRemoteDescription(new RTCSessionDescription(signal.offer));
                    const answer = await peerConnection.createAnswer();
                    await peerConnection.setLocalDescription(answer);
                    ws.send(JSON.stringify({ type: 'answer', answer: answer }));

                    callBtn.disabled = true;
                    callBtn.textContent = "Звонок активен...";
                } else if (signal.type === 'answer') {
                    await peerConnection.setRemoteDescription(new RTCSessionDescription(signal.answer));
                } else if (signal.type === 'ice-candidate') {
                    await peerConnection.addIceCandidate(new RTCIceCandidate(signal.candidate));
                }
                
            } catch (e) {
                // Если это не сигнал WebRTC, значит, это зашифрованное сообщение чата
                try {
                    const decryptedPayloadString = decryptMessage(event.data, encryptionKey);
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
                } catch (err) {
                    console.error("Не удалось обработать сообщение:", err);
                }
            }
        };

        form.addEventListener('submit', (event) => {
            event.preventDefault();
            if (input.value && ws && ws.readyState === WebSocket.OPEN) {
                const messageData = { message: input.value, ttl: parseInt(ttlSelect.value, 10) };
                const encryptedPayload = encryptMessage(messageData, encryptionKey);
                ws.send(encryptedPayload);
                input.value = '';
            }
        });
    }
});