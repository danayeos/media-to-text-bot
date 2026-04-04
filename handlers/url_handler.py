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
        },

        # Попытаться имитировать браузер Chrome (помогает с TikTok)
        "impersonate": "chrome120",
    }

    try:
        await status_msg.edit_text("⏳ Скачиваю аудио со ссылки...")

        # Запустить загрузку
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Сначала получить информацию о видео (без скачивания)
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "видео")
            duration = info.get("duration", 0)

            # Проверить длительность — Whisper медленно обрабатывает длинные файлы
            if duration and duration > 10800:  # больше 3 часов
                await status_msg.edit_text(
                    "⚠️ Видео слишком длинное (больше 3 часов).\n\n"
                    "Отправь видео короче 3 часов."
                )
                return

            await status_msg.edit_text(f"⏳ Скачиваю: *{title[:50]}*...", parse_mode="Markdown")

            # Скачать файл
            ydl.download([url])

        # Найти скачанный файл (yt-dlp сам добавляет расширение)
        audio_path = _find_downloaded_file(output_template)
        if not audio_path:
            await status_msg.edit_text("❌ Не удалось найти скачанный файл.")
            return

        # Сохранить путь к файлу для обработки после нажатия кнопки языка
        context.user_data["pending"] = {
            "type": "audio",
            "path": audio_path,
        }

        await status_msg.edit_text(
            f"✅ Скачано: *{title[:60]}*\n\nВыберите язык записи:",
            parse_mode="Markdown",
            reply_markup=LANGUAGE_KEYBOARD,
        )

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        logger.error(f"yt-dlp download error: {error_msg}")

        if "Private" in error_msg or "private" in error_msg:
            reason = "Это приватное видео — бот не может его скачать."
        elif "not available" in error_msg:
            reason = "Видео недоступно в вашем регионе или удалено."
        elif "Sign in" in error_msg or "login" in error_msg.lower():
            reason = "Это видео требует входа в аккаунт (Instagram/TikTok private)."
        elif "copyright" in error_msg.lower():
            reason = "Видео заблокировано по авторским правам."
        else:
            reason = "Убедитесь что ссылка открывается в браузере."

        await status_msg.edit_text(
            f"❌ Не удалось скачать видео.\n\n{reason}"
        )

    except Exception as e:
        logger.error(f"URL handler error: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Ошибка: {e}\n\n"
            "Попробуйте другую ссылку."
        )


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
