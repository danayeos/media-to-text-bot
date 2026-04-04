# =============================================================================
# config.py — Central configuration for the Media-to-Text Bot
# Edit this file to change bot settings
# =============================================================================

import os
from dotenv import load_dotenv

# Load variables from .env file (if it exists)
# This lets you keep your secret token outside the code
load_dotenv()

# ─── REQUIRED ────────────────────────────────────────────────────────────────
# Your Telegram bot token — get it from @BotFather on Telegram
# Store it in .env file as:  BOT_TOKEN=123456:ABCdef...
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ─── WHISPER SETTINGS ────────────────────────────────────────────────────────
# Model size controls speed vs accuracy trade-off:
#   "tiny"   → fastest,  lowest accuracy  (~75 MB RAM)
#   "base"   → fast,     decent accuracy  (~145 MB RAM)  ← recommended
#   "small"  → medium,   good accuracy    (~466 MB RAM)
#   "medium" → slow,     great accuracy   (~1.5 GB RAM)
#   "large"  → slowest,  best accuracy    (~3 GB RAM)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# Language for transcription:
#   None  → auto-detect language (recommended)
#   "en"  → force English
#   "ru"  → force Russian
#   "kk"  → force Kazakh
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE") or None  # None = auto-detect

# ─── TESSERACT OCR SETTINGS ──────────────────────────────────────────────────
# Languages for OCR — you must install matching language packs for Tesseract
# "eng"             → English only
# "eng+rus"         → English + Russian
# "eng+rus+kaz"     → all three (needs kaz.traineddata installed)
TESSERACT_LANG = os.getenv("TESSERACT_LANG", "eng+rus")

# ─── FILE LIMITS ─────────────────────────────────────────────────────────────
# Telegram Bot API limits file downloads to 20 MB on free tier
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))

# ─── PATHS ───────────────────────────────────────────────────────────────────
# Directory for temporary downloaded files (auto-created at startup)
TEMP_DIR = "temp_files"

# Path to Tesseract executable
# Windows: C:\Program Files\Tesseract-OCR\tesseract.exe
# Linux (Docker/Railway): /usr/bin/tesseract  ← устанавливается автоматически
import platform
_default_tesseract = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if platform.system() == "Windows"
    else "/usr/bin/tesseract"
)
TESSERACT_CMD = os.getenv("TESSERACT_CMD", _default_tesseract)
