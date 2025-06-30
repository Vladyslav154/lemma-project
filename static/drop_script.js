document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const resultZone = document.getElementById('result-zone');
    const downloadLink = document.getElementById('download-link');
    const copyButton = document.getElementById('copy-button');
    const dropZoneText = dropZone.querySelector('p');

    // Открываем диалог выбора файла по клику на зону
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileUpload(fileInput.files[0]);
        }
    });

    // Обработка перетаскивания файла
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    // Главная функция загрузки файла
    async function handleFileUpload(file) {
        dropZoneText.textContent = 'Загрузка...';
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Ошибка при загрузке файла.');
            }

            const result = await response.json();
            showResult(result.download_link);

        } catch (error) {
            console.error(error);
            dropZoneText.textContent = 'Произошла ошибка. Попробуйте снова.';
        }
    }

    // Показываем результат
    function showResult(link) {
        const fullLink = `${window.location.origin}${link}`;
        dropZone.style.display = 'none';
        resultZone.style.display = 'block';
        downloadLink.href = fullLink;
        downloadLink.textContent = fullLink;
    }
    
    // Копирование ссылки в буфер обмена
    copyButton.addEventListener('click', () => {
        navigator.clipboard.writeText(downloadLink.href).then(() => {
            copyButton.textContent = 'Скопировано!';
            setTimeout(() => {
                copyButton.textContent = 'Копировать ссылку';
            }, 2000);
        });
    });
});