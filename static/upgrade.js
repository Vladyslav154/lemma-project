// static/upgrade.js
document.addEventListener('DOMContentLoaded', () => {
    const monthlyBtn = document.getElementById('monthly-btn');
    const yearlyBtn = document.getElementById('yearly-btn');
    const keyDisplay = document.getElementById('key-display');
    const accessKeyElement = document.getElementById('access-key');

    const generateKey = async (planType) => {
        // Показываем пользователю, что что-то происходит
        keyDisplay.style.display = 'block';
        accessKeyElement.textContent = 'Генерация ключа...';

        try {
            const response = await fetch('/keys/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `plan_type=${planType}`
            });

            if (!response.ok) {
                throw new Error('Произошла ошибка при создании ключа.');
            }

            const data = await response.json();
            accessKeyElement.textContent = data.access_key;

        } catch (error) {
            accessKeyElement.textContent = error.message;
        }
    };

    monthlyBtn.addEventListener('click', () => generateKey('monthly'));
    yearlyBtn.addEventListener('click', () => generateKey('yearly'));
});