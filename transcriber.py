import logging
import os

logger = logging.getLogger(__name__)

_client = None


def load_model(model_size: str = "base"):
    """No-op: Groq Whisper API needs no local model."""
    logger.info("Using Groq Whisper API (whisper-large-v3-turbo) — no local model needed.")
    return True


def _get_client():
    global _client
    if _client is None:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Get a free key at console.groq.com")
        _client = Groq(api_key=api_key)
    return _client


def transcribe_audio(audio_path: str, language: str | None = None) -> dict:
    """
    Transcribe audio via Groq Whisper API (free, no RAM needed).
    Requires GROQ_API_KEY env variable.
    """
    client = _get_client()

    logger.info(f"Transcribing via Groq: {audio_path} | language={language or 'auto'}")

    kwargs = {"model": "whisper-large-v3-turbo", "response_format": "verbose_json"}
    if language:
        kwargs["language"] = language

    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(file=f, **kwargs)

    text = response.text.strip()
    detected_lang = getattr(response, "language", language or "unknown")

    logger.info(f"Transcription done. Language: {detected_lang} | Length: {len(text)} chars")

    return {
        "text": text,
        "language": detected_lang,
        "confidence": 1.0,
    }
