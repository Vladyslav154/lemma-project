document.addEventListener('DOMContentLoaded', () => {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const fileNameDisplay = document.getElementById('file-name');
    const uploadButton = document.getElementById('upload-button');
    const linkArea = document.getElementById('link-area');
    const fileLink = document.getElementById('file-link');
    const qrcodeContainer = document.getElementById('qrcode');

    uploadArea.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            fileNameDisplay.textContent = `Выбран файл: ${file.name}`;
            uploadButton.style.display = 'block';
        }
    });

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

            // --- ИЗМЕНЕНИЕ ЗДЕСЬ: Добавляем ключ в заголовки запроса ---
            const headers = {};
            const accessKey = localStorage.getItem('lepko_access_key');
            if (accessKey) {
                headers['Authorization'] = `Bearer ${accessKey}`;
            }

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
                headers: headers // <-- Передаем заголовки
            });
            // --- КОНЕЦ ИЗМЕНЕНИЯ ---

            // Если пришла ошибка, показываем ее текст
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Ошибка при загрузке файла.');
            }

            const result = await response.json();
            const link = `${window.location.origin}/file/${result.file_id}`;
            
            fileLink.href = link;
            fileLink.textContent = link;
            
            qrcodeContainer.innerHTML = "";
            new QRCode(qrcodeContainer, {
                text: link,
                width: 128,
                height: 128,
            });

            linkArea.style.display = 'block';

        } catch (error) {
            console.error('Ошибка:', error);
            alert(error.message);
        } finally {
            uploadButton.textContent = 'Получить ссылку';
            uploadButton.disabled = false;
        }
    });
});