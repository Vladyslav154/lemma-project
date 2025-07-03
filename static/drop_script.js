document.addEventListener('DOMContentLoaded', () => {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const fileNameDisplay = document.getElementById('file-name');
    const uploadButton = document.getElementById('upload-button');
    const linkArea = document.getElementById('link-area');
    const fileLink = document.getElementById('file-link');
    const qrcodeContainer = document.getElementById('qrcode');

    // Открыть выбор файла по клику на область
    uploadArea.addEventListener('click', () => fileInput.click());

    // Обработка выбора файла
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            fileNameDisplay.textContent = `Выбран файл: ${file.name}`;
            uploadButton.style.display = 'block';
        }
    });

    // Обработка загрузки по клику на кнопку
    uploadButton.addEventListener('click', async () => {
        if (fileInput.files.length === 0) {
            alert('Пожалуйста, выберите файл для загрузки.');
            return;
        }

        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);

        try {
            uploadButton.textContent = 'Загрузка...';
            uploadButton.disabled = true;

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Ошибка при загрузке файла. Попробуйте снова.');
            }

            const result = await response.json();
            const link = `${window.location.origin}/file/${result.file_id}`;
            
            // Показываем ссылку
            fileLink.href = link;
            fileLink.textContent = link;
            linkArea.style.display = 'block';

            // --- НОВЫЙ БЛОК: ГЕНЕРАЦИЯ QR-КОДА ---
            qrcodeContainer.innerHTML = ""; // Очищаем старый QR-код
            new QRCode(qrcodeContainer, {
                text: link,
                width: 128,
                height: 128,
            });
            // --- КОНЕЦ НОВОГО БЛОКА ---

        } catch (error) {
            console.error('Ошибка:', error);
            alert(error.message);
        } finally {
            uploadButton.textContent = 'Получить ссылку';
            uploadButton.disabled = false;
        }
    });
});