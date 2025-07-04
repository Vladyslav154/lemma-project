document.addEventListener('DOMContentLoaded', () => {
    const monthlyBtn = document.getElementById('monthly-btn');
    const yearlyBtn = document.getElementById('yearly-btn');
    const keyDisplay = document.getElementById('key-display');
    const accessKeyElem = document.getElementById('access-key');

    const handlePlanSelection = async (planType) => {
        const formData = new FormData();
        formData.append('plan_type', planType);

        try {
            // Показываем пользователю, что что-то происходит
            keyDisplay.style.display = 'none';
            if (planType === 'monthly') {
                monthlyBtn.textContent = 'Создание счета...';
                monthlyBtn.disabled = true;
            } else {
                yearlyBtn.textContent = 'Создание счета...';
                yearlyBtn.disabled = true;
            }

            const response = await fetch('/keys/generate', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok && data.payment_url) {
                // --- ГЛАВНОЕ ИЗМЕНЕНИЕ: Перенаправляем на страницу оплаты ---
                window.location.href = data.payment_url;
            } else {
                // Показываем ошибку, если что-то пошло не так
                accessKeyElem.textContent = `Ошибка: ${data.detail || 'Не удалось создать ссылку на оплату.'}`;
                keyDisplay.style.display = 'block';
            }

        } catch (error) {
            console.error('Ошибка:', error);
            accessKeyElem.textContent = 'Произошла критическая ошибка. Попробуйте позже.';
            keyDisplay.style.display = 'block';
        } finally {
            // Возвращаем кнопки в исходное состояние
            if (planType === 'monthly') {
                monthlyBtn.textContent = 'Получить ключ';
                monthlyBtn.disabled = false;
            } else {
                yearlyBtn.textContent = 'Получить ключ';
                yearlyBtn.disabled = false;
            }
        }
    };

    monthlyBtn.addEventListener('click', () => handlePlanSelection('monthly'));
    yearlyBtn.addEventListener('click', () => handlePlanSelection('yearly'));
});