# =============================================================================
# translator.py — Optional translation feature (BONUS)
#
# Uses deep-translator library which provides free translation
# via Google Translate (no API key required, rate-limited).
#
# Supported direction examples:
#   Russian  → English
#   Kazakh   → English
#   English  → Russian
#   etc.
# =============================================================================

import logging
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

# Language code mapping from Whisper codes to Google Translate codes
# (they are slightly different for some languages)
WHISPER_TO_GOOGLE = {
    "kk": "kk",   # Kazakh
    "ru": "ru",   # Russian
    "en": "en",   # English
    "de": "de",   # German
    "fr": "fr",   # French
    "zh": "zh-CN",  # Chinese (Simplified)
    "ja": "ja",   # Japanese
    "ar": "ar",   # Arabic
}

# Human-readable language names for display
LANGUAGE_NAMES = {
    "kk": "Kazakh 🇰🇿",
    "ru": "Russian 🇷🇺",
    "en": "English 🇬🇧",
    "de": "German 🇩🇪",
    "fr": "French 🇫🇷",
    "zh": "Chinese 🇨🇳",
    "ja": "Japanese 🇯🇵",
    "ar": "Arabic 🇸🇦",
}


def translate_text(text: str, source_lang: str, target_lang: str = "en") -> str:
    """
    Translate text from one language to another using Google Translate (free).

    Args:
        text:        The text to translate
        source_lang: Source language code (e.g. "ru", "kk")
                     Use "auto" to let Google detect the language
        target_lang: Target language code (default: "en" = English)

    Returns:
        Translated text string

    Raises:
        Exception: If translation fails (e.g. no internet connection)
    """
    if not text or not text.strip():
        return ""

    # Map Whisper language code to Google Translate code
    source = WHISPER_TO_GOOGLE.get(source_lang, source_lang)
    target = WHISPER_TO_GOOGLE.get(target_lang, target_lang)

    logger.info(f"Translating from '{source}' to '{target}' | {len(text)} chars")

    # Google Translate has a character limit per request (~5000 chars)
    # Split into chunks if text is too long
    if len(text) > 4500:
        chunks = split_text(text, max_length=4500)
        translated_chunks = []
        for chunk in chunks:
            translated = _translate_chunk(chunk, source, target)
            translated_chunks.append(translated)
        return " ".join(translated_chunks)

    return _translate_chunk(text, source, target)


def _translate_chunk(text: str, source: str, target: str) -> str:
    """Translate a single chunk of text."""
    translator = GoogleTranslator(source=source, target=target)
    result = translator.translate(text)
    return result or text  # Return original if translation is None


def split_text(text: str, max_length: int = 4500) -> list[str]:
    """Split long text into chunks at sentence boundaries."""
    # Split at sentence endings: ., !, ?
    sentences = []
    current = []
    current_len = 0

    # Simple sentence splitting by punctuation
    for char in text:
        current.append(char)
        current_len += 1
        if char in ".!?\n" and current_len >= 100:
            sentences.append("".join(current))
            current = []
            current_len = 0

    if current:
        sentences.append("".join(current))

    # Group sentences into chunks
    chunks = []
    current_chunk = []
    current_chunk_len = 0

    for sentence in sentences:
        if current_chunk_len + len(sentence) > max_length and current_chunk:
            chunks.append("".join(current_chunk))
            current_chunk = [sentence]
            current_chunk_len = len(sentence)
        else:
            current_chunk.append(sentence)
            current_chunk_len += len(sentence)

    if current_chunk:
        chunks.append("".join(current_chunk))

    return chunks


def get_language_name(code: str) -> str:
    """Get human-readable language name from code."""
    return LANGUAGE_NAMES.get(code, code.upper())
