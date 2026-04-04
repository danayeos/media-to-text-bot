# =============================================================================
# utils/cookies.py — Управление куки для yt-dlp
#
# YouTube, TikTok, Instagram требуют куки браузера для скачивания.
# Один файл cookies.txt содержит куки для всех сайтов.
# Хранится в переменной BROWSER_COOKIES на Railway.
# =============================================================================

import os
import logging
import tempfile

logger = logging.getLogger(__name__)

_cookies_file_path: str | None = None


def init_cookies() -> None:
    """
    Прочитать куки из переменной окружения и записать во временный файл.
    Проверяет BROWSER_COOKIES (новое имя) и TIKTOK_COOKIES (старое, для совместимости).
    """
    global _cookies_file_path

    # Поддерживаем оба имени переменной
    cookies_content = (
        os.getenv("BROWSER_COOKIES", "") or
        os.getenv("TIKTOK_COOKIES", "")
    ).strip()

    if not cookies_content:
        logger.info("BROWSER_COOKIES не задан — YouTube/Instagram/TikTok могут не работать.")
        return

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    tmp.write(cookies_content)
    tmp.close()

    _cookies_file_path = tmp.name
    logger.info(f"Куки браузера загружены → {_cookies_file_path}")


def get_cookies_file() -> str | None:
    """Вернуть путь к файлу с куки или None если не настроены."""
    return _cookies_file_path
