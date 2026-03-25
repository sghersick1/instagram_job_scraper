"""Content Extraction — in-memory OCR from story image bytes."""

import io
import re

from PIL import Image, ImageFilter, ImageEnhance
import pytesseract

from scraper import StoryFrame


# ---------------------------------------------------------------------------
# OCR (operates on bytes — no disk I/O)
# ---------------------------------------------------------------------------

def _ocr_bytes(image_bytes: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)
        return pytesseract.image_to_string(img, config="--psm 6").strip()
    except Exception as exc:
        print(f"[extractor] OCR failed: {exc}")
        return ""


# ---------------------------------------------------------------------------
# URL extraction from raw text
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s\"'>]+")


def _extract_urls_from_text(text: str) -> list[str]:
    return _URL_RE.findall(text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract(frame: StoryFrame) -> dict:
    """
    Given a StoryFrame, return:
      - raw_text: OCR'd text from the story image (in memory, no disk writes)
      - links: deduplicated list of destination URLs
    """
    raw_text = _ocr_bytes(frame.image_bytes) if frame.image_bytes else ""

    all_links = list(frame.links)
    for url in _extract_urls_from_text(raw_text):
        if url not in all_links:
            all_links.append(url)

    return {
        "raw_text": raw_text,
        "links": all_links,
    }
