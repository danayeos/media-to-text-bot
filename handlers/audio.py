# =============================================================================
# handlers/audio.py — Handle audio files and voice messages
# =============================================================================

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

import config
from transcriber import transcribe_audio
from utils.files import download_telegram_file, cleanup_files

logger = logging.getLogger(__name__)

# Language selection keyboard shown to user before transcribing
LANGUAGE_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🇰🇿 Казахский", callback_data="lang:kk"),
        InlineKeyboardButton("🇷🇺 Русский",   callback_data="lang:ru"),
    ],
    [
        InlineKeyboardButton("🇬🇧 English",   callback_data="lang:en"),
        InlineKeyboardButton("🌐 Авто",        callback_data="lang:auto"),
    ],
])


def _get_audio_size(message) -> int:
    if message.audio:
        return message.audio.file_size or 0
    if message.voice:
        return message.voice.file_size or 0
    if message.document:
        return message.document.file_size or 0
    return 0


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle audio files and voice messages.
    Downloads the file, then asks user to choose language via inline buttons.
    """
    message = update.message

    # Size check
    size_bytes = _get_audio_size(message)
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > config.MAX_FILE_SIZE_MB:
        await message.reply_text(
            f"❌ Файл слишком большой ({size_mb:.1f} MB).\n"
            f"Максимум: {config.MAX_FILE_SIZE_MB} MB."
        )
        return

    status_msg = await message.reply_text("⏳ Скачиваю аудио...")

    try:
        file_path, _ = await download_telegram_file(message, config.TEMP_DIR)

        # Save pending file for when user clicks a language button
        context.user_data["pending"] = {"type": "audio", "path": file_path}

        await status_msg.edit_text(
            "🎵 Аудио получено. Выберите язык записи:",
            reply_markup=LANGUAGE_KEYBOARD,
        )
    except Exception as e:
        logger.error(f"Audio download error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка при скачивании: {e}")


async def process_audio(file_path: str, language: str | None, status_msg, source: str = "🎵 Аудио"):
    """
    Transcribe audio file and edit status_msg with the result.
    Called from the language callback handler.
    """
    try:
        await status_msg.edit_text("🔄 Транскрибирую речь...", reply_markup=None)

        result = transcribe_audio(file_path, language=language)

        # ── AI коррекция ошибок Whisper ───────────────────────────────────
        from ai_corrector import correct_transcription, is_available
        if is_available() and result["text"]:
            await status_msg.edit_text("🤖 ИИ исправляет текст...", reply_markup=None)
            result["text"] = correct_transcription(result["text"], result["language"])

        if not result["text"]:
            await status_msg.edit_text(
                "⚠️ Речь не обнаружена.\n\n"
                "Возможные причины:\n"
                "• Аудио тихое или с шумом\n"
                "• Выбран неверный язык\n"
                "• Файл повреждён"
            )
            return

        await _send_result(status_msg, result, source)

    except Exception as e:
        logger.error(f"Audio transcription error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка транскрипции: {e}", reply_markup=None)
    finally:
        cleanup_files(file_path)


async def _send_result(status_msg, result: dict, source: str):
    """Send transcription result. Escapes Markdown to avoid parse errors."""
    from translator import get_language_name, translate_text

    text = result["text"]
    lang_code = result.get("language", "?")
    confidence = result.get("confidence", 0)
    lang_name = get_language_name(lang_code)

    # Translate to Russian if source language is not already Russian
    translated_text = None
    if lang_code != "ru":
        try:
            await status_msg.edit_text("🌐 Перевожу на русский...", reply_markup=None)
            translated_text = translate_text(text, source_lang=lang_code, target_lang="ru")
        except Exception as e:
            logger.warning(f"Translation failed: {e}")

    # escape_markdown makes *, _, `, [ safe inside Markdown messages
    safe_text = escape_markdown(text, version=1)

    if translated_text:
        safe_translated = escape_markdown(translated_text, version=1)
        response = (
            f"{source} → *Транскрипция ({lang_name}):*\n\n"
            f"{safe_text}\n\n"
            f"──────────────\n"
            f"🇷🇺 *Перевод на русский:*\n\n"
            f"{safe_translated}\n\n"
            f"──────────────\n"
            f"🌐 Язык оригинала: {lang_name} ({confidence:.0%})"
        )
    else:
        response = (
            f"{source} → *Транскрипция:*\n\n"
            f"{safe_text}\n\n"
            f"──────────────\n"
            f"🌐 Язык: {lang_name} ({confidence:.0%})"
        )

    if len(response) <= 4096:
        await status_msg.edit_text(response, parse_mode="Markdown", reply_markup=None)
    else:
        # Header without text
        await status_msg.edit_text(
            f"{source} → *Транскрипция:* _(длинный текст, разбит на части)_",
            parse_mode="Markdown",
            reply_markup=None,
        )
        # Send original text in plain chunks
        remaining = text
        while remaining:
            await status_msg.reply_text(remaining[:4096])
            remaining = remaining[4096:]
        # Send translation if available
        if translated_text:
            await status_msg.reply_text("🇷🇺 Перевод на русский:")
            remaining = translated_text
            while remaining:
                await status_msg.reply_text(remaining[:4096])
                remaining = remaining[4096:]
        # Footer
        await status_msg.reply_text(f"🌐 Язык оригинала: {lang_name} ({confidence:.0%})")
