// static/activate.js
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('activation-form');
    const input = document.getElementById('key-input');
    const statusDiv = document.getElementById('activation-status');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const key = input.value.trim();
        if (!key) {
            statusDiv.textContent = 'Пожалуйста, введите ключ.';
            return;
        }

        try {
            const response = await fetch(`/keys/check/${key}`);
            const data = await response.json();

            if (response.ok && data.status === 'active') {
                // Ключ верный! Сохраняем его в локальное хранилище браузера.
                localStorage.setItem('lepko_access_key', key);
                statusDiv.style.color = '#00ffff';
                statusDiv.textContent = `Ключ успешно активирован! План: ${data.plan}.`;
            } else {
                // Ключ неверный или истек.
                localStorage.removeItem('lepko_access_key');
                statusDiv.style.color = '#e94560';
                statusDiv.textContent = data.detail || 'Неверный ключ или срок его действия истек.';
            }

        } catch (error) {
            statusDiv.style.color = '#e94560';
            statusDiv.textContent = 'Произошла ошибка при проверке ключа.';
        }
    });
});