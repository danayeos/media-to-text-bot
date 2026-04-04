# =============================================================================
# Dockerfile — инструкция для сборки контейнера на сервере
#
# Railway читает этот файл и автоматически:
#   1. Берёт базовый образ Python 3.11
#   2. Устанавливает ffmpeg и Tesseract OCR (системные программы)
#   3. Устанавливает Python-пакеты из requirements.txt
#   4. Запускает bot.py
# =============================================================================

# Базовый образ — Python 3.11 на Debian Linux (лёгкая версия)
FROM python:3.11-slim

# Установить системные зависимости:
#   ffmpeg              → для извлечения аудио из видео
#   tesseract-ocr       → движок OCR
#   tesseract-ocr-rus   → языковой пакет: русский
#   tesseract-ocr-kaz   → языковой пакет: казахский
RUN apt-get update && apt-get install -y \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-kaz \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория внутри контейнера
WORKDIR /app

# Сначала копируем только requirements.txt и устанавливаем пакеты
# (Docker кэширует этот слой — пересборка быстрее если код изменился, а зависимости нет)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код проекта
COPY . .

# Создать папку для временных файлов
RUN mkdir -p temp_files

# Команда запуска бота
CMD ["python", "bot.py"]
