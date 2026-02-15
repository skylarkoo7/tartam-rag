from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)

try:
    from pdf2image import convert_from_path  # type: ignore
    import pytesseract  # type: ignore
except Exception:  # pragma: no cover - optional dependencies
    convert_from_path = None
    pytesseract = None


@dataclass(slots=True)
class PageText:
    page_number: int
    text: str
    extraction_method: str
    quality_score: float


class PDFExtractionError(RuntimeError):
    pass


def _text_quality_score(text: str) -> float:
    if not text:
        return 0.0

    printable = sum(1 for ch in text if ch.isprintable())
    alpha = sum(1 for ch in text if ch.isalpha())
    weird = len(re.findall(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", text))

    printable_ratio = printable / max(len(text), 1)
    alpha_ratio = alpha / max(len(text), 1)
    weird_ratio = weird / max(len(text), 1)

    return max(0.0, min(1.0, (0.6 * printable_ratio) + (0.6 * alpha_ratio) - (2.0 * weird_ratio)))


def extract_pdf_pages(pdf_path: Path, enable_ocr_fallback: bool = False) -> tuple[list[PageText], int]:
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:  # pragma: no cover - parser dependent
        raise PDFExtractionError(f"Could not open PDF: {pdf_path}") from exc

    if reader.is_encrypted:
        unlocked = False
        for pwd in ("", " ", None):
            try:
                if pwd is None:
                    continue
                if reader.decrypt(pwd):
                    unlocked = True
                    break
            except Exception:
                continue
        if not unlocked:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise PDFExtractionError(
                    f"Could not decrypt PDF: {pdf_path}. Ensure pycryptodome is installed for AES PDFs."
                ) from exc

    pages: list[PageText] = []
    ocr_pages = 0

    try:
        page_objects = list(reader.pages)
    except Exception as exc:
        raise PDFExtractionError(
            f"Could not read PDF pages for {pdf_path}. "
            "AES decryption support may be missing (install pycryptodome)."
        ) from exc

    for idx, page in enumerate(page_objects, start=1):
        raw = ""
        try:
            raw = page.extract_text() or ""
        except Exception:
            raw = ""

        quality = _text_quality_score(raw)
        method = "pdf"

        text = raw
        if enable_ocr_fallback and quality < 0.12:
            ocr = _extract_page_ocr(pdf_path, idx)
            if ocr:
                text = ocr
                method = "ocr"
                quality = _text_quality_score(text)
                ocr_pages += 1

        pages.append(
            PageText(
                page_number=idx,
                text=text,
                extraction_method=method,
                quality_score=quality,
            )
        )

    return pages, ocr_pages


def _extract_page_ocr(pdf_path: Path, page_number: int) -> str:
    if convert_from_path is None or pytesseract is None:
        logger.warning("OCR dependencies missing; skipping OCR fallback for %s page %s", pdf_path, page_number)
        return ""

    try:  # pragma: no cover - OCR integration
        images = convert_from_path(str(pdf_path), first_page=page_number, last_page=page_number, dpi=300)
        if not images:
            return ""
        text = pytesseract.image_to_string(images[0], lang="hin+guj+eng")
        return text or ""
    except Exception:
        logger.exception("OCR failed for %s page %s", pdf_path, page_number)
        return ""
