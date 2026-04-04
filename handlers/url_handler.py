# =============================================================================
# handlers/url_handler.py — Скачать аудио по ссылке и транскрибировать
#
# Поддерживает: YouTube, TikTok, Instagram, Twitter/X, VK, Twitch и 1000+ сайтов
# Использует yt-dlp (бесплатно, без API ключей)
#
# Поток:
#   Ссылка → yt-dlp скачивает аудио → выбор языка → Whisper → ИИ → текст
# =============================================================================

import logging
import os
import re
import uuid

import yt_dlp

import config
from handlers.audio import LANGUAGE_KEYBOARD, process_audio
from utils.cookies import get_cookies_file

logger = logging.getLogger(__name__)

# Регулярное выражение для определения ссылок в тексте
URL_PATTERN = re.compile(r"https?://[^\s]+")

# Поддерживаемые домены (для информативного сообщения пользователю)
SUPPORTED_SITES = [
    "youtube.com", "youtu.be",
    "tiktok.com",
    "instagram.com",
    "twitter.com", "x.com",
    "vk.com",
    "twitch.tv",
    "facebook.com",
    "reddit.com",
    "soundcloud.com",
]


def extract_url(text: str) -> str | None:
    """Извлечь первую ссылку из текста сообщения."""
    match = URL_PATTERN.search(text)
    return match.group(0) if match else None


async def handle_url(update, context):
    """
    Обработать сообщение со ссылкой.
    Скачивает аудио с помощью yt-dlp, затем показывает кнопки выбора языка.
    """
    message = update.message
    text = message.text or ""

    url = extract_url(text)
    if not url:
        return  # Нет ссылки в сообщении — игнорируем

    status_msg = await message.reply_text("🔗 Получаю информацию о видео...")

    # Уникальное имя файла чтобы несколько пользователей не конфликтовали
    output_template = os.path.join(config.TEMP_DIR, f"{uuid.uuid4().hex}.%(ext)s")

    # Настройки yt-dlp
    ydl_opts = {
        # Скачать только аудио (не видео) — экономит время и место
        "format": "bestaudio/best",

        # Конвертировать в WAV через ffmpeg (оптимально для Whisper)
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],

        # Путь сохранения файла
        "outtmpl": output_template,

        # Тихий режим — не выводить прогресс в консоль
        "quiet": True,
        "no_warnings": True,

        # Ограничение размера: не скачивать файлы больше 100MB
        "max_filesize": 100 * 1024 * 1024,

        # Заголовки браузера — TikTok и Instagram блокируют запросы без них
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.tiktok.com/",
        },
    }

    # Добавить куки если есть (нужно для TikTok и Instagram)
    cookies_file = get_cookies_file()
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

    try:
        await status_msg.edit_text("⏳ Скачиваю аудио со ссылки...")

        title = "видео"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Получить инфо и скачать за один раз
            # extract_info с download=True делает всё сразу
            info = ydl.extract_info(url, download=True)
            if info:
                title = info.get("title", "видео")
                duration = info.get("duration", 0)
                if duration and duration > 10800:
                    await status_msg.edit_text(
                        "⚠️ Видео слишком длинное (больше 3 часов)."
                    )
                    return

        # Найти скачанный файл
        audio_path = _find_downloaded_file(output_template)
        if not audio_path:
            await status_msg.edit_text(
                "❌ Файл скачан, но не найден. Попробуйте ещё раз."
            )
            return

        context.user_data["pending"] = {"type": "audio", "path": audio_path}

        # Безопасно экранируем title для Markdown
        safe_title = title[:60].replace("*", "").replace("_", "").replace("`", "")
        await status_msg.edit_text(
            f"✅ Скачано: *{safe_title}*\n\nВыберите язык записи:",
            parse_mode="Markdown",
            reply_markup=LANGUAGE_KEYBOARD,
        )

    except yt_dlp.utils.DownloadError as e:
        # Показываем реальную ошибку yt-dlp для диагностики
        raw = str(e)
        logger.error(f"yt-dlp DownloadError: {raw}")

        # Определяем понятную причину
        low = raw.lower()
        if "private" in low:
            reason = "Приватное видео."
        elif "login" in low or "sign in" in low:
            reason = "Требуется вход в аккаунт."
        elif "copyright" in low:
            reason = "Заблокировано по авторским правам."
        elif "not available" in low or "unavailable" in low:
            reason = "Видео удалено или недоступно."
        else:
            reason = f"Детали: {raw[-200:]}"  # последние 200 символов реальной ошибки

        await status_msg.edit_text(f"❌ Не удалось скачать.\n\n{reason}")

    except Exception as e:
        logger.error(f"URL handler error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка: {e}")


def _find_downloaded_file(output_template: str) -> str | None:
    """
    Найти файл скачанный yt-dlp.
    yt-dlp заменяет %(ext)s на реальное расширение (wav, mp3, etc.),
    поэтому ищем файл по базовому имени.
    """
    # Базовое имя без %(ext)s
    base = output_template.replace(".%(ext)s", "")

    # Проверить возможные расширения
    for ext in (".wav", ".mp3", ".m4a", ".ogg", ".opus", ".webm", ".mp4"):
        candidate = base + ext
        if os.path.exists(candidate):
            return candidate

    # Если не нашли — поискать в папке по базовому имени
    folder = os.path.dirname(base)
    prefix = os.path.basename(base)
    if os.path.exists(folder):
        for filename in os.listdir(folder):
            if filename.startswith(prefix):
                return os.path.join(folder, filename)

    return None
