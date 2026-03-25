"""Content Extraction — OCR + text cleanup per story frame."""

import re
from pathlib import Path

from PIL import Image, ImageFilter, ImageEnhance
import pytesseract

from scraper import StoryFrame


# ---------------------------------------------------------------------------
# OCR preprocessing
# ---------------------------------------------------------------------------

def _preprocess_for_ocr(image_path: str) -> Image.Image:
    img = Image.open(image_path).convert("L")          # grayscale
    img = ImageEnhance.Contrast(img).enhance(2.0)      # boost contrast
    img = img.filter(ImageFilter.SHARPEN)              # sharpen edges
    return img


def _ocr_screenshot(screenshot_path: str) -> str:
    try:
        img = _preprocess_for_ocr(screenshot_path)
        text = pytesseract.image_to_string(img, config="--psm 6")
        return text.strip()
    except Exception as exc:
        print(f"[extractor] OCR failed for {screenshot_path}: {exc}")
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
    Given a StoryFrame, return a dict with:
      - raw_text: story text (DOM overlays preferred; OCR fallback if DOM is empty)
      - links: deduplicated list of destination URLs

    Instagram stories are videos — DOM text overlays render regardless of playback.
    OCR is unreliable when video fails to load, so it is only used if DOM yields nothing.
    """
    raw_text = frame.dom_text.strip()

    # OCR fallback: only if DOM extracted nothing useful
    if not raw_text:
        ocr_text = _ocr_screenshot(frame.screenshot_path)
        if ocr_text:
            raw_text = ocr_text

    # Links come from the scraper's DOM link extraction (l.instagram.com decoder)
    # Also catch any plain URLs that appear in text stickers
    all_links = list(frame.links)
    for url in _extract_urls_from_text(raw_text):
        if url not in all_links:
            all_links.append(url)

    return {
        "raw_text": raw_text,
        "links": all_links,
    }
