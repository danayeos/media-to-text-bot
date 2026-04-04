# =============================================================================
# utils/files.py — File download and cleanup utilities
#
# These helper functions handle:
#   - Downloading files from Telegram to local disk
#   - Extracting audio from video using ffmpeg
#   - Deleting temporary files after processing
# =============================================================================

import os
import logging
import subprocess
from pathlib import Path

from telegram import Message

logger = logging.getLogger(__name__)


async def download_telegram_file(message: Message, temp_dir: str) -> tuple[str, str]:
    """
    Download a file from a Telegram message to a local temp folder.

    Supports: audio, voice, video, video_note, photo, document

    Args:
        message:  The Telegram message object
        temp_dir: Directory path to save the downloaded file

    Returns:
        A tuple of (local_file_path, media_type)
        media_type is one of: "audio", "video", "image"

    Raises:
        ValueError: If the message contains no downloadable file
    """
    os.makedirs(temp_dir, exist_ok=True)

    # ── Determine what type of file is in the message ──────────────────────
    if message.audio:
        # Audio file (mp3, wav, etc. sent as audio)
        tg_file = await message.audio.get_file()
        # Try to keep the original extension; fallback to .mp3
        original_name = message.audio.file_name or "audio.mp3"
        ext = Path(original_name).suffix or ".mp3"
        media_type = "audio"

    elif message.voice:
        # Voice message (recorded in Telegram, .ogg format)
        tg_file = await message.voice.get_file()
        ext = ".ogg"
        media_type = "audio"

    elif message.video:
        # Video file
        tg_file = await message.video.get_file()
        ext = ".mp4"
        media_type = "video"

    elif message.video_note:
        # Video circle (the round video messages in Telegram)
        tg_file = await message.video_note.get_file()
        ext = ".mp4"
        media_type = "video"

    elif message.photo:
        # Photo — Telegram sends multiple sizes; we take the largest ([-1])
        tg_file = await message.photo[-1].get_file()
        ext = ".jpg"
        media_type = "image"

    elif message.document:
        # File sent as a document — we'll check its type by extension/MIME
        tg_file = await message.document.get_file()
        name = message.document.file_name or "file"
        ext = Path(name).suffix.lower() or ".bin"
        mime = message.document.mime_type or ""

        if mime.startswith("audio/") or ext in (".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"):
            media_type = "audio"
        elif mime.startswith("video/") or ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
            media_type = "video"
        elif mime.startswith("image/") or ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
            media_type = "image"
        else:
            raise ValueError(
                f"Unsupported file type: {ext} ({mime})\n\n"
                "Supported formats:\n"
                "• Audio: MP3, WAV, OGG, M4A, FLAC\n"
                "• Video: MP4, AVI, MOV, MKV\n"
                "• Image: JPG, PNG, BMP, TIFF"
            )
    else:
        raise ValueError("No downloadable file found in this message.")

    # ── Download the file ──────────────────────────────────────────────────
    # Use file_unique_id to avoid collisions when multiple users send files
    save_path = os.path.join(temp_dir, f"{tg_file.file_unique_id}{ext}")
    await tg_file.download_to_drive(save_path)
    logger.info(f"Downloaded {media_type} file → {save_path}")

    return save_path, media_type


def extract_audio_from_video(video_path: str) -> str:
    """
    Extract the audio track from a video file using ffmpeg.

    Whisper works best with:
      - WAV format (uncompressed)
      - 16,000 Hz sample rate
      - Mono channel

    Args:
        video_path: Full path to the video file

    Returns:
        Full path to the extracted WAV audio file

    Raises:
        RuntimeError: If ffmpeg fails or is not installed
        FileNotFoundError: If the video file doesn't exist
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Output path: same name as video but with _audio.wav suffix
    audio_path = video_path.rsplit(".", 1)[0] + "_audio.wav"

    # Build the ffmpeg command
    # Explanation of each flag:
    #   -y              → overwrite output file if it already exists
    #   -i video_path   → input file
    #   -vn             → no video (extract audio only)
    #   -acodec pcm_s16le → WAV format (16-bit PCM, little-endian)
    #   -ar 16000       → 16,000 Hz sample rate (what Whisper expects)
    #   -ac 1           → mono channel (1 channel, not stereo)
    command = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path,
    ]

    logger.info(f"Extracting audio: {video_path} → {audio_path}")

    # Run ffmpeg — capture both stdout and stderr
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    # Check if ffmpeg succeeded (return code 0 = success)
    if result.returncode != 0:
        error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
        raise RuntimeError(
            f"ffmpeg failed to extract audio.\n\n"
            f"Error: {error_msg}\n\n"
            "Make sure ffmpeg is installed:\n"
            "  Windows: https://ffmpeg.org/download.html\n"
            "  Or run: winget install ffmpeg"
        )

    logger.info(f"Audio extracted successfully → {audio_path}")
    return audio_path


def cleanup_files(*file_paths: str | None):
    """
    Delete one or more temporary files from disk.

    It's safe to pass None values — they will be skipped.
    Used in finally blocks to ensure temp files are always cleaned up.

    Example:
        cleanup_files(video_path, audio_path)
    """
    for path in file_paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"Deleted temp file: {path}")
            except OSError as e:
                # Non-fatal: log but don't crash if deletion fails
                logger.warning(f"Could not delete temp file {path}: {e}")


def get_file_size_mb(file_path: str) -> float:
    """Return the file size in megabytes."""
    return os.path.getsize(file_path) / (1024 * 1024)
