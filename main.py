import os
from flask import Flask, render_template, request, send_from_directory, session
from werkzeug.utils import secure_filename
import secrets

# Импортируем наш новый класс
from translator import Translator

app = Flask(__name__)

# Конфигурация
app.config['UPLOAD_FOLDER'] = 'temp_uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB
app.secret_key = secrets.token_hex(16)

# Создаем папку для загрузок, если ее нет
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Инициализируем переводчик
translator = Translator(app)

# --- Маршруты (Routes) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/drop', methods=['GET', 'POST'])
def drop():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file part"
        file = request.files['file']
        if file.filename == '':
            return "No selected file"
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            download_link = request.host_url + 'uploads/' + filename
            return render_template('drop_success.html', link=download_link)
    return render_template('drop.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/pad', methods=['GET'])
def pad():
    return render_template('pad.html')

@app.route('/upgrade')
def upgrade():
    return render_template('upgrade.html')

if __name__ == '__main__':
    app.run(debug=True)