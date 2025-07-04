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
    const voiceMaskLabel = document.getElementById('voice-mask-label');
    const voiceMaskCheckbox = document.getElementById('voice-mask-checkbox');

    let ws;
    let encryptionKey = '';
    let peerConnection;
    let localStream;
    let audioContext;
    const servers = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

    // --- ИСПРАВЛЕНИЕ: Генерируем URL СРАЗУ при загрузке страницы ---
    let boardId = window.location.pathname.split('/pad/')[1];
    if (!boardId || boardId.trim() === '') {
        boardId = Math.random().toString(36).substring(2, 12);
        window.history.replaceState({}, document.title, `/pad/${boardId}`);
    }
    // --- КОНЕЦ ИСПРАВЛЕНИЯ ---

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
    
    const handleWebRTCSignal = async (signal) => {
        try {
            if (!peerConnection && (signal.type === 'answer' || signal.type === 'ice-candidate')) return;
            if (!peerConnection) await setupPeerConnection(false);

            if (signal.type === 'offer') {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(signal.offer));
                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);
                sendMessageToServer('webrtc', { type: 'answer', answer: answer });
            } else if (signal.type === 'answer') {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(signal.answer));
            } else if (signal.type === 'ice-candidate') {
                if (peerConnection.signalingState !== "closed") {
                    await peerConnection.addIceCandidate(new RTCIceCandidate(signal.candidate));
                }
            }
        } catch (e) { console.error("Ошибка WebRTC:", e); }
    };

    const setupPeerConnection = async (isInitiator) => {
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        peerConnection = new RTCPeerConnection(servers);
        
        audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(localStream);
        const destination = audioContext.createMediaStreamDestination();
        const biquadFilter = audioContext.createBiquadFilter();
        biquadFilter.type = "lowshelf";
        biquadFilter.frequency.setValueAtTime(1000, audioContext.currentTime);
        biquadFilter.gain.setValueAtTime(25, audioContext.currentTime);
        source.connect(biquadFilter);
        biquadFilter.connect(destination);

        let streamToSend = voiceMaskCheckbox.checked ? destination.stream : localStream;
        streamToSend.getTracks().forEach(track => peerConnection.addTrack(track, streamToSend));

        voiceMaskCheckbox.addEventListener('change', () => {
            const newStream = voiceMaskCheckbox.checked ? destination.stream : localStream;
            const sender = peerConnection.getSenders().find(s => s.track.kind === 'audio');
            sender.replaceTrack(newStream.getAudioTracks()[0]);
        });

        peerConnection.ontrack = event => { remoteAudio.srcObject = event.streams[0]; };
        peerConnection.onicecandidate = event => {
            if (event.candidate) sendMessageToServer('webrtc', { type: 'ice-candidate', candidate: event.candidate });
        };
        
        callBtn.disabled = true;
        callBtn.textContent = "Звонок активен...";
        voiceMaskLabel.style.display = 'flex';

        if (isInitiator) {
            const offer = await peerConnection.createOffer();
            await peerConnection.setLocalDescription(offer);
            sendMessageToServer('webrtc', { type: 'offer', offer: offer });
        }
    };

    const initializeWebSocket = () => {
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
            displayChatMessage(messageData);
            const encryptedPayload = encryptMessage(messageData, encryptionKey);
            sendMessageToServer('chat', encryptedPayload);
            input.value = '';
        }
    });

    callBtn.addEventListener('click', () => setupPeerConnection(true));
});