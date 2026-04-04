# =============================================================================
# ocr_processor.py — Extract text from images using Tesseract OCR
#
# Tesseract is a free, open-source OCR engine originally developed by HP,
# now maintained by Google. It supports 100+ languages including
# Kazakh, Russian, and English.
# =============================================================================

import logging
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import config

# Tell pytesseract exactly where tesseract.exe is located on Windows.
# Without this, it can't find it even if Tesseract is installed.
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

logger = logging.getLogger(__name__)


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Improve image quality before OCR to get better results.

    Steps:
      1. Convert to grayscale (removes color noise)
      2. Increase contrast (makes text stand out more)
      3. Slightly sharpen (makes blurry text more readable)

    Args:
        image: PIL Image object

    Returns:
        Processed PIL Image object
    """
    # Step 1: Convert to grayscale
    image = image.convert("L")

    # Step 2: Increase contrast (1.0 = original, 2.0 = double contrast)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)

    # Step 3: Sharpen the image
    image = image.filter(ImageFilter.SHARPEN)

    return image


def extract_text_from_image(image_path: str, lang: str = "eng+rus") -> str:
    """
    Extract all text visible in an image using Tesseract OCR.

    Args:
        image_path: Full path to the image file (JPG, PNG, BMP, TIFF, etc.)
        lang:       Tesseract language string.
                    Use "+" to combine languages, e.g. "eng+rus+kaz"
                    Language codes:
                      eng → English
                      rus → Russian
                      kaz → Kazakh (requires kaz.traineddata to be installed)

    Returns:
        Extracted text as a string. Empty string if no text found.
    """
    logger.info(f"Running OCR on: {image_path} | lang={lang}")

    # Open the image file with Pillow
    original_image = Image.open(image_path)

    # Preprocess the image for better accuracy
    processed_image = preprocess_image(original_image)

    # Run Tesseract OCR
    # --oem 3  → Use the best OCR engine (LSTM neural network)
    # --psm 3  → Fully automatic page segmentation (default)
    #            Other useful values:
    #              6 → Assume a single uniform block of text
    #             11 → Treat as sparse text, find as much text as possible
    custom_config = "--oem 3 --psm 3"

    raw_text = pytesseract.image_to_string(
        processed_image,
        lang=lang,
        config=custom_config,
    )

    # Clean up: remove leading/trailing whitespace and extra blank lines
    lines = [line.strip() for line in raw_text.splitlines()]
    clean_lines = [line for line in lines if line]  # remove empty lines
    result = "\n".join(clean_lines)

    logger.info(f"OCR done. Extracted {len(result)} characters.")
    return result


def try_ocr_with_fallback(image_path: str, preferred_lang: str = "eng+rus") -> str:
    """
    Try OCR with the preferred language combination.
    If it fails (e.g. language pack not installed), fall back to English only.

    This is useful because not all users have Kazakh language packs installed.

    Args:
        image_path:    Full path to the image file
        preferred_lang: Preferred language string (may fall back if unavailable)

    Returns:
        Extracted text string
    """
    # Build a list of languages to try, from most preferred to least
    # For example, "eng+rus+kaz" → try "eng+rus+kaz", then "eng+rus", then "eng"
    lang_parts = preferred_lang.split("+")

    # Try progressively simpler language combinations
    attempts = []
    for i in range(len(lang_parts), 0, -1):
        attempts.append("+".join(lang_parts[:i]))

    for lang in attempts:
        try:
            logger.info(f"Trying OCR with lang='{lang}'")
            text = extract_text_from_image(image_path, lang=lang)
            logger.info(f"OCR succeeded with lang='{lang}'")
            return text
        except Exception as e:
            logger.warning(f"OCR failed with lang='{lang}': {e}")
            continue

    # If all attempts fail, raise the error
    raise RuntimeError(
        "OCR failed. Make sure Tesseract is installed and language packs are available.\n"
        "Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki"
    )
