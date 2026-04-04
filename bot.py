# =============================================================================
# bot.py — Main entry point for the Media-to-Text Telegram Bot
#
# Run this file to start the bot:
#   python bot.py
#
# What this bot does:
#   🎵 Audio  → transcribes speech to text using Whisper AI (local, free)
#   🎬 Video  → extracts audio with ffmpeg, then transcribes with Whisper
#   🖼️ Image  → extracts printed text using Tesseract OCR (local, free)
#
# Supports: Kazakh, Russian, English (and 90+ other languages for audio)
# Works fully offline — no paid APIs needed
# =============================================================================

import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Local modules
import config
from transcriber import load_model
from handlers.audio import handle_audio
from handlers.video import handle_video
from handlers.image import handle_image

# ─── Logging setup ────────────────────────────────────────────────────────────
# This prints timestamped logs to the console so you can see what the bot is doing
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# =============================================================================
# COMMAND HANDLERS — respond to /commands
# =============================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start — Welcome message shown when user first opens the bot."""
    text = (
        "👋 *Добро пожаловать в Media-to-Text Bot!*\n\n"
        "Я конвертирую медиафайлы и ссылки в текст:\n\n"
        "🎵 *Аудио* → Отправь аудиофайл или голосовое сообщение\n"
        "🎬 *Видео* → Отправь видеофайл\n"
        "🖼️ *Фото* → Отправь фото с текстом\n"
        "🔗 *Ссылка* → Вставь ссылку на TikTok, Instagram и др.\n\n"
        "Просто отправь файл или ссылку — я сделаю остальное!\n\n"
        "Используй /help для подробностей."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help — Show usage instructions."""
    text = (
        "ℹ️ *How to use this bot:*\n\n"
        "1. Send me an audio, video, or image file\n"
        "2. Wait while I process it\n"
        "3. I'll reply with the extracted text\n\n"
        "─────────────────\n"
        "*Supported file formats:*\n"
        "• Audio: MP3, WAV, OGG, M4A, FLAC, AAC\n"
        "• Video: MP4, AVI, MOV, MKV, WEBM\n"
        "• Image: JPG, PNG, BMP, TIFF, WEBP\n\n"
        "*File size limit:* 20 MB\n\n"
        "─────────────────\n"
        "*Languages (audio/video):*\n"
        "Auto-detected. Works with:\n"
        "🇰🇿 Kazakh  🇷🇺 Russian  🇬🇧 English\n"
        "and 97 more languages!\n\n"
        "*Languages (images):*\n"
        "English + Russian (+ Kazakh if installed)\n\n"
        "─────────────────\n"
        "*Commands:*\n"
        "/start — Welcome message\n"
        "/help — This message\n"
        "/setlang — Set transcription language\n"
        "/lang — Show current language setting\n"
        "/translate — Translate last result to English"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_setlang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setlang [code] — Set the transcription language for audio/video."""
    valid_langs = {
        "auto": "Auto-detect 🌐",
        "en": "English 🇬🇧",
        "ru": "Russian 🇷🇺",
        "kk": "Kazakh 🇰🇿",
        "de": "German 🇩🇪",
        "fr": "French 🇫🇷",
        "zh": "Chinese 🇨🇳",
        "ar": "Arabic 🇸🇦",
        "tr": "Turkish 🇹🇷",
    }

    if not context.args:
        # Show available options if no argument given
        options = "\n".join(f"`/setlang {code}` — {name}" for code, name in valid_langs.items())
        await update.message.reply_text(
            f"*Set Transcription Language*\n\n{options}\n\n"
            f"Example: `/setlang ru` for Russian",
            parse_mode="Markdown",
        )
        return

    lang = context.args[0].lower().strip()

    if lang not in valid_langs:
        await update.message.reply_text(
            f"❌ Unknown language code: `{lang}`\n\n"
            f"Use `/setlang` to see valid options.",
            parse_mode="Markdown",
        )
        return

    # Save language preference in this user's session
    # context.user_data persists for the lifetime of the bot process
    context.user_data["language"] = None if lang == "auto" else lang

    await update.message.reply_text(
        f"✅ Language set to: *{valid_langs[lang]}*\n\n"
        f"This will apply to all future audio/video transcriptions.",
        parse_mode="Markdown",
    )


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/lang — Show the current language setting."""
    lang = context.user_data.get("language") or "auto"
    lang_names = {
        "auto": "Auto-detect 🌐", "en": "English 🇬🇧",
        "ru": "Russian 🇷🇺", "kk": "Kazakh 🇰🇿",
    }
    display = lang_names.get(lang, lang.upper())
    await update.message.reply_text(
        f"🌐 Current language: *{display}*\n\nUse `/setlang` to change it.",
        parse_mode="Markdown",
    )


async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/translate — Translate the last transcription result to English."""
    last_text = context.user_data.get("last_text")
    last_lang = context.user_data.get("last_lang", "auto")

    if not last_text:
        await update.message.reply_text(
            "⚠️ No recent transcription to translate.\n\n"
            "Send me an audio, video, or image first!",
        )
        return

    if last_lang == "en":
        await update.message.reply_text("ℹ️ The last result is already in English.")
        return

    status_msg = await update.message.reply_text("🔄 *Translating to English...*", parse_mode="Markdown")

    try:
        from translator import translate_text
        translated = translate_text(last_text, source_lang=last_lang, target_lang="en")
        await status_msg.edit_text(
            f"🌐 *Translation (English):*\n\n{translated}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Translation error: {e}")
        await status_msg.edit_text(
            f"❌ Translation failed: `{e}`\n\nCheck your internet connection.",
            parse_mode="Markdown",
        )


# =============================================================================
# DOCUMENT HANDLER — route documents to correct handler by type
# =============================================================================

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Route documents (files sent without compression) to the right handler.

    When a user sends a file in Telegram as a "document" (instead of photo/audio),
    we check its MIME type and extension to decide how to process it.
    """
    message = update.message
    doc = message.document

    if not doc:
        return

    mime = (doc.mime_type or "").lower()
    name = (doc.file_name or "").lower()

    if mime.startswith("audio/") or any(name.endswith(e) for e in (".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac")):
        await handle_audio(update, context)

    elif mime.startswith("video/") or any(name.endswith(e) for e in (".mp4", ".avi", ".mov", ".mkv", ".webm")):
        await handle_video(update, context)

    elif mime.startswith("image/") or any(name.endswith(e) for e in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp")):
        await handle_image(update, context)

    else:
        await message.reply_text(
            "❌ *Unsupported file type.*\n\n"
            "Send me:\n"
            "• Audio: MP3, WAV, OGG, M4A, FLAC\n"
            "• Video: MP4, AVI, MOV, MKV\n"
            "• Image: JPG, PNG, BMP, TIFF",
            parse_mode="Markdown",
        )


# =============================================================================
# FALLBACK HANDLER — handle plain text or unsupported messages
# =============================================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработать текстовое сообщение.
    Если это ссылка — передать в url_handler.
    Если просто текст — попросить отправить файл.
    """
    from handlers.url_handler import handle_url, extract_url

    text = update.message.text or ""

    # Проверяем — есть ли ссылка в сообщении
    if extract_url(text):
        await handle_url(update, context)
        return

    # Обычный текст — объяснить что бот умеет
    await update.message.reply_text(
        "ℹ️ Отправьте мне файл или ссылку:\n\n"
        "🎵 Аудио файл / голосовое сообщение\n"
        "🎬 Видео файл\n"
        "🖼️ Фото с текстом\n"
        "🔗 Ссылка на YouTube, TikTok, Instagram...\n\n"
        "Используй /help для подробностей."
    )


# =============================================================================
# LANGUAGE BUTTON CALLBACK — triggered when user clicks 🇰🇿 🇷🇺 🇬🇧 🌐 button
# =============================================================================

async def handle_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Called when user clicks a language selection button (InlineKeyboardButton).
    Reads the pending file from user_data and starts transcription.

    callback_data format: "lang:kk" | "lang:ru" | "lang:en" | "lang:auto"
    """
    query = update.callback_query
    await query.answer()  # Remove the "loading" spinner on the button

    # Parse which language was chosen
    _, lang_code = query.data.split(":")
    language = None if lang_code == "auto" else lang_code

    # Get the pending file info stored when the file was downloaded
    pending = context.user_data.get("pending")
    if not pending:
        await query.edit_message_text("⚠️ Файл не найден. Отправьте аудио/видео снова.")
        return

    # Clear pending so it can't be processed twice
    context.user_data.pop("pending", None)

    file_path = pending["path"]
    media_type = pending["type"]

    # Transcribe using the chosen language
    from handlers.audio import process_audio
    source = "🎵 Аудио" if media_type == "audio" else "🎬 Видео"
    await process_audio(file_path, language=language, status_msg=query.message, source=source)


# =============================================================================
# ERROR HANDLER — catch unexpected errors so the bot doesn't crash
# =============================================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log unexpected errors."""
    logger.error("Unhandled exception:", exc_info=context.error)

    # If there's an update with a message, notify the user
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again.\n"
            "If the problem persists, try a different file."
        )


# =============================================================================
# MAIN — start the bot
# =============================================================================

def main():
    """Build and start the Telegram bot."""

    # ── Validate configuration ────────────────────────────────────────────
    if not config.BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN is not set!\n\n"
            "Steps to fix:\n"
            "1. Create a .env file in this folder\n"
            "2. Add this line: BOT_TOKEN=your_token_here\n"
            "3. Get your token from @BotFather on Telegram"
        )

    # ── Create temp directory for downloaded files ────────────────────────
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    logger.info(f"Temp directory: {os.path.abspath(config.TEMP_DIR)}")

    # ── Load cookies for TikTok/Instagram ────────────────────────────────
    from utils.cookies import init_cookies
    init_cookies()

    # ── Load Whisper model once at startup ────────────────────────────────
    # This takes 10-60 seconds. We do it here so users don't wait on first message.
    logger.info(f"Loading Whisper model '{config.WHISPER_MODEL}'...")
    load_model(config.WHISPER_MODEL)

    # ── Build the Telegram bot application ───────────────────────────────
    app = Application.builder().token(config.BOT_TOKEN).build()

    # ── Register command handlers (/commands) ─────────────────────────────
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("setlang", cmd_setlang))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("translate", cmd_translate))

    # ── Register media handlers ───────────────────────────────────────────
    # filters.AUDIO    → audio files (mp3, wav, etc.)
    # filters.VOICE    → voice messages recorded in Telegram
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))

    # filters.VIDEO      → video files
    # filters.VIDEO_NOTE → circular video messages
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))

    # filters.PHOTO → compressed photos sent in Telegram
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    # filters.Document.ALL → files sent without compression ("as document")
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # ── Language selection button callbacks ───────────────────────────────
    # pattern="^lang:" matches callback_data starting with "lang:"
    app.add_handler(CallbackQueryHandler(handle_language_callback, pattern="^lang:"))

    # ── Fallback for plain text ───────────────────────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # ── Register global error handler ────────────────────────────────────
    app.add_error_handler(error_handler)

    # ── Start polling ─────────────────────────────────────────────────────
    # Polling means the bot keeps asking Telegram "any new messages?"
    # This works anywhere — no public URL needed (unlike webhooks)
    logger.info("✅ Bot is running! Press Ctrl+C to stop.")
    logger.info("Open Telegram and send a message to your bot.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
