# =============================================================================
# handlers/image.py — Handle photos and image files
# =============================================================================

import logging
from telegram import Update
from telegram.ext import ContextTypes

import config
from ocr_processor import try_ocr_with_fallback
from utils.files import download_telegram_file, cleanup_files

logger = logging.getLogger(__name__)

# Telegram max message size is 4096 chars
TELEGRAM_MAX_LENGTH = 4096


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle photos and image documents sent to the bot.

    Flow:
      1. Download the image
      2. Run Tesseract OCR
      3. Reply with extracted text
      4. Delete temp file
    """
    message = update.message

    # ── Step 1: Notify user ───────────────────────────────────────────────
    status_msg = await message.reply_text(
        "🖼️ *Scanning image for text...*\nPlease wait.",
        parse_mode="Markdown",
    )

    file_path = None
    try:
        # ── Step 2: Download image ────────────────────────────────────────
        file_path, _ = await download_telegram_file(message, config.TEMP_DIR)

        # ── Step 3: Run OCR ───────────────────────────────────────────────
        # try_ocr_with_fallback tries "eng+rus+kaz", then "eng+rus", then "eng"
        # in case some language packs are not installed
        text = try_ocr_with_fallback(file_path, preferred_lang=config.TESSERACT_LANG)

        # ── Step 4: Reply ─────────────────────────────────────────────────
        if not text:
            await status_msg.edit_text(
                "⚠️ *No text found in this image.*\n\n"
                "Tips for better results:\n"
                "• Use a high-resolution image\n"
                "• Make sure text is clearly visible\n"
                "• Avoid blurry or rotated images\n"
                "• Ensure good contrast between text and background",
                parse_mode="Markdown",
            )
            return

        # ── Step 5: Translate to Russian ──────────────────────────────
        translated_text = None
        try:
            from translator import translate_text
            await status_msg.edit_text("🌐 Перевожу на русский...")
            translated_text = translate_text(text, source_lang="auto", target_lang="ru")
        except Exception as e:
            logger.warning(f"Translation failed: {e}")

        # Send the header with Markdown, then the raw OCR text WITHOUT parse_mode.
        # OCR text can contain *, _, `, [ etc. which break Telegram's Markdown parser.
        await status_msg.edit_text("🖼️ Распознанный текст:")
        await _send_long_message(status_msg, message, text)

        if translated_text:
            await message.reply_text("🇷🇺 Перевод на русский:")
            await _send_long_message(status_msg, message, translated_text)

    except Exception as e:
        logger.error(f"Image handler error: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ *Failed to process image.*\n\n`{e}`\n\n"
            f"Make sure Tesseract OCR is installed correctly.",
            parse_mode="Markdown",
        )
    finally:
        # ── Step 5: Cleanup ───────────────────────────────────────────────
        cleanup_files(file_path)


async def _send_long_message(status_msg, original_message, text: str):
    """
    Send a potentially long message, splitting it if needed.
    Telegram allows max 4096 characters per message.
    No parse_mode — OCR text may contain special characters that break Markdown.
    """
    if len(text) <= TELEGRAM_MAX_LENGTH:
        await original_message.reply_text(text)
        return

    # Send in chunks
    remaining = text
    part = 1
    while remaining:
        chunk = remaining[:TELEGRAM_MAX_LENGTH]
        await original_message.reply_text(chunk)
        remaining = remaining[TELEGRAM_MAX_LENGTH:]
        part += 1
