# =============================================================================
# ai_corrector.py — Исправление ошибок транскрипции с помощью ИИ (Groq, бесплатно)
#
# После того как Whisper перевёл аудио в текст, этот модуль отправляет текст
# в языковую модель (Llama 3), которая исправляет ошибки распознавания по смыслу.
#
# Это особенно полезно для казахского языка, где Whisper иногда ошибается.
# =============================================================================

import logging
import os

logger = logging.getLogger(__name__)

# Имена языков для промпта
_LANG_NAMES = {
    "kk": "Kazakh (қазақ тілі)",
    "ru": "Russian (русский)",
    "en": "English",
    "de": "German",
    "fr": "French",
}

# Groq клиент — создаётся один раз
_client = None


def _get_client():
    """Создать Groq клиент (один раз)."""
    global _client
    if _client is None:
        try:
            from groq import Groq
            api_key = os.getenv("GROQ_API_KEY", "")
            if not api_key:
                return None
            _client = Groq(api_key=api_key)
        except ImportError:
            logger.warning("groq пакет не установлен. AI-коррекция недоступна.")
            return None
    return _client


def correct_transcription(text: str, language: str) -> str:
    """
    Отправить транскрибированный текст в Groq LLM для исправления ошибок.

    Модель анализирует текст по смыслу и исправляет:
      - Неправильно распознанные слова
      - Пропущенные слова
      - Явные грамматические ошибки от Whisper

    Args:
        text:     Текст после Whisper транскрипции
        language: Код языка ("kk", "ru", "en" и др.)

    Returns:
        Исправленный текст. Если Groq недоступен — возвращает оригинал.
    """
    client = _get_client()

    # Если нет API ключа или клиента — вернуть текст без изменений
    if not client or not text.strip():
        return text

    lang_name = _LANG_NAMES.get(language, language.upper())

    # Промпт объясняет модели задачу
    prompt = (
        f"You are a speech transcription correction assistant.\n\n"
        f"The text below was transcribed from audio using Whisper speech recognition "
        f"and may contain errors: wrong words, missing words, or unclear phrases.\n\n"
        f"Language: {lang_name}\n\n"
        f"Instructions:\n"
        f"- Fix transcription mistakes based on context and meaning\n"
        f"- Keep the SAME language as the original\n"
        f"- Do NOT change the meaning, style, or content\n"
        f"- Do NOT add explanations or comments\n"
        f"- Return ONLY the corrected text\n\n"
        f"Text to correct:\n{text}"
    )

    try:
        response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Лучшая бесплатная модель Groq
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,   # Низкая температура = точнее, меньше фантазии
            max_tokens=2048,
        )
        corrected = response.choices[0].message.content.strip()
        logger.info(f"AI коррекция: {len(text)} → {len(corrected)} символов")
        return corrected

    except Exception as e:
        # Если Groq недоступен (нет интернета, лимит) — вернуть оригинал
        logger.warning(f"AI коррекция не удалась: {e}. Возвращаю оригинал.")
        return text


def is_available() -> bool:
    """Проверить доступен ли AI корректор (есть ли API ключ)."""
    return bool(os.getenv("GROQ_API_KEY", ""))
