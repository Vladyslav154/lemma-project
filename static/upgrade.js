document.addEventListener('DOMContentLoaded', () => {
    const monthlyBtn = document.getElementById('monthly-btn');
    const yearlyBtn = document.getElementById('yearly-btn');
    const trialBtn = document.getElementById('trial-btn');
    const keyDisplay = document.getElementById('key-display');
    const accessKeyElem = document.getElementById('access-key');

    const handlePlanSelection = async (planType) => {
        const formData = new FormData();
        formData.append('plan_type', planType);

        try {
            const btn = (planType === 'monthly') ? monthlyBtn : yearlyBtn;
            btn.textContent = 'Создание счета...';
            btn.disabled = true;

            const response = await fetch('/keys/generate', { method: 'POST', body: formData });
            const data = await response.json();

            if (response.ok && data.payment_url) {
                window.location.href = data.payment_url;
            } else {
                accessKeyElem.textContent = `Ошибка: ${data.detail || 'Не удалось создать ссылку.'}`;
                keyDisplay.style.display = 'block';
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    };

    const handleTrialSelection = async () => {
        trialBtn.disabled = true;
        trialBtn.textContent = 'Генерация...';
        try {
            const response = await fetch('/keys/generate_trial', { method: 'POST' });
            const data = await response.json();
            keyDisplay.style.display = 'block';
            if (response.ok) {
                accessKeyElem.textContent = data.access_key;
            } else {
                accessKeyElem.textContent = `Ошибка: ${data.detail || 'Не удалось сгенерировать ключ.'}`;
            }
        } catch (error) {
            console.error('Ошибка:', error);
        } finally {
            trialBtn.disabled = false;
        }
    };

    monthlyBtn.addEventListener('click', () => handlePlanSelection('monthly'));
    yearlyBtn.addEventListener('click', () => handlePlanSelection('yearly'));
    trialBtn.addEventListener('click', handleTrialSelection);
});