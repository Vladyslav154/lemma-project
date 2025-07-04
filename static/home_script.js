document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('/stats');
        const data = await response.json();
        document.getElementById('stats-keys').textContent = data.keys_generated || 0;
        document.getElementById('stats-files').textContent = data.files_transferred || 0;
    } catch (error) {
        console.error("Не удалось загрузить статистику:", error);
    }
});