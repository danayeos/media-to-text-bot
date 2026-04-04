# =============================================================================
# transcriber.py — Audio transcription using faster-whisper (runs locally, free)
#
# faster-whisper is a reimplementation of Whisper that:
#   - Does NOT need PyTorch (much lighter install)
#   - Is 4x faster than the original Whisper on CPU
#   - Uses less RAM
#   - Supports the same languages (Kazakh, Russian, English, etc.)
# =============================================================================

import logging
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Global model variable — we load the model ONCE when the bot starts,
# not on every request. Loading takes 5-30 seconds, so we do it once.
# ─────────────────────────────────────────────────────────────────────────────
_model: WhisperModel | None = None


def load_model(model_size: str = "base") -> WhisperModel:
    """
    Load the Whisper model into memory.
    Call this once at bot startup.

    Args:
        model_size: "tiny", "base", "small", "medium", or "large"

    Returns:
        The loaded WhisperModel instance
    """
    global _model

    if _model is not None:
        logger.info("Whisper model already loaded, reusing.")
        return _model

    logger.info(f"Loading Whisper model '{model_size}'... (this may take 30 seconds)")

    # device="cpu"         → run on CPU (works everywhere, no GPU required)
    # compute_type="int8"  → use 8-bit integers (faster + less RAM than float32)
    _model = WhisperModel(model_size, device="cpu", compute_type="int8")

    logger.info("Whisper model loaded successfully!")
    return _model


def transcribe_audio(audio_path: str, language: str | None = None) -> dict:
    """
    Transcribe an audio file to text.

    Args:
        audio_path: Full path to the audio file (WAV, MP3, OGG, etc.)
        language:   Language code to force, e.g. "ru", "en", "kk"
                    Pass None to let Whisper auto-detect the language.

    Returns:
        A dict with two keys:
          - "text"     : The transcribed text (string)
          - "language" : The detected language code (e.g. "ru", "en")
    """
    if _model is None:
        raise RuntimeError(
            "Whisper model is not loaded! Call load_model() before transcribing."
        )

    logger.info(f"Transcribing: {audio_path} | language={language or 'auto'}")

    # transcribe() returns:
    #   segments → iterable of text chunks (with timestamps)
    #   info     → metadata including detected language
    try:
        segments, info = _model.transcribe(
            audio_path,
            language=language,          # None = auto-detect per segment
            beam_size=5,                # Higher = more accurate, slower
            vad_filter=True,            # Skip silent parts (Voice Activity Detection)
            vad_parameters=dict(
                min_silence_duration_ms=500  # Ignore silences < 0.5 second
            ),
            word_timestamps=False,
        )
        segment_list = list(segments)

    except ValueError:
        # "max() arg is an empty sequence" — VAD удалил все сегменты (тишина/шум).
        # Повторяем без VAD фильтра чтобы всё же попробовать распознать.
        logger.warning("VAD filter removed all segments, retrying without VAD...")
        segments, info = _model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=False,  # отключаем VAD
            word_timestamps=False,
        )
        segment_list = list(segments)

    # Join all text chunks into one string.
    full_text = " ".join(seg.text.strip() for seg in segment_list)

    detected_lang = info.language  # e.g. "ru", "en", "kk"

    logger.info(
        f"Transcription done. Language: {detected_lang} | "
        f"Confidence: {info.language_probability:.0%} | "
        f"Length: {len(full_text)} chars"
    )

    return {
        "text": full_text.strip(),
        "language": detected_lang,
        "confidence": round(info.language_probability, 2),
    }
