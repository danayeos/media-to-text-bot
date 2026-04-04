# =============================================================================
# handlers/video.py — Handle video files
#
# Process flow:
#   Video → download → ffmpeg extracts audio → user picks language → Whisper
# =============================================================================

import logging
from telegram import Update
from telegram.ext import ContextTypes

import config
from utils.files import download_telegram_file, extract_audio_from_video, cleanup_files
from handlers.audio import LANGUAGE_KEYBOARD

logger = logging.getLogger(__name__)


def _get_video_size(message) -> int:
    if message.video:
        return message.video.file_size or 0
    if message.video_note:
        return message.video_note.file_size or 0
    if message.document:
        return message.document.file_size or 0
    return 0


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle video files sent to the bot.
    Downloads + extracts audio, then asks user to pick language via buttons.
    """
    message = update.message

    size_bytes = _get_video_size(message)
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > config.MAX_FILE_SIZE_MB:
        await message.reply_text(
            f"❌ Файл слишком большой ({size_mb:.1f} MB).\n"
            f"Максимум: {config.MAX_FILE_SIZE_MB} MB."
        )
        return

    status_msg = await message.reply_text("⏳ Скачиваю видео...")

    video_path = None
    audio_path = None
    try:
        video_path, _ = await download_telegram_file(message, config.TEMP_DIR)

        await status_msg.edit_text("🔄 Извлекаю аудио из видео...")
        audio_path = extract_audio_from_video(video_path)

        # Store extracted audio path — video_path can be deleted now
        cleanup_files(video_path)
        video_path = None

        context.user_data["pending"] = {"type": "video", "path": audio_path}

        await status_msg.edit_text(
            "🎬 Видео получено. Выберите язык записи:",
            reply_markup=LANGUAGE_KEYBOARD,
        )
    except Exception as e:
        logger.error(f"Video handler error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка: {e}", reply_markup=None)
        cleanup_files(video_path, audio_path)
