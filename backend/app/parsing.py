from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .language import detect_style, normalize_text, transliterate_to_latin
from .pdf_extract import PageText


_PRAKRAN_PATTERN = re.compile(r"(प्रकरण|પકરણ|पकरण|prakran|prakaran)", re.IGNORECASE)
_CHOPAI_MARKER_PATTERN = re.compile(r"(॥\s*\d+|\b\d+\s*$|JJ\s*\d+|\]\s*\d+\s*$)", re.IGNORECASE)
_PRAKRAN_NUM_PREFIX = re.compile(r"^\s*[-–—]\s*(\d{1,3})\s*[-–—]\s*(.*)$")


@dataclass(slots=True)
class ParsedUnit:
    granth_name: str
    prakran_name: str
    chopai_number: str | None
    prakran_chopai_index: int | None
    chopai_lines: list[str]
    meaning_text: str
    language_script: str
    page_number: int
    pdf_path: str
    source_set: str
    normalized_text: str
    translit_hi_latn: str
    translit_gu_latn: str
    chunk_text: str
    chunk_type: str


def parse_pdf_to_units(pdf_path: Path, pages: list[PageText]) -> list[ParsedUnit]:
    granth = infer_granth_name(pdf_path)
    source_set = infer_source_set(pdf_path)
    current_prakran = "Unknown Prakran"

    units: list[ParsedUnit] = []

    for page in pages:
        page_units, current_prakran = _parse_page(granth, source_set, pdf_path, page, current_prakran)
        units.extend(page_units)

    if not units:
        return []
    counters: dict[tuple[str, str], int] = {}
    for unit in units:
        key = (unit.granth_name, unit.prakran_name)
        counters[key] = counters.get(key, 0) + 1
        unit.prakran_chopai_index = counters[key]
    return units


def infer_granth_name(pdf_path: Path) -> str:
    name = pdf_path.stem
    name = re.sub(r"^[0-9]+", "", name).strip()
    name = name.replace("GCM", "").strip("-_ ")
    return name or pdf_path.stem


def infer_source_set(pdf_path: Path) -> str:
    lower = str(pdf_path.parent).lower()
    if "hindi-arth" in lower:
        return "hindi-arth"
    if "guj-arth" in lower:
        return "guj-arth"
    return "unknown"


def _clean_lines(text: str) -> list[str]:
    lines = [normalize_text(line) for line in (text or "").splitlines()]
    result: list[str] = []
    for line in lines:
        if not line:
            continue
        # Keep -14- style markers because many Tartam PDFs encode prakran this way.
        # Only drop plain page-number-like lines.
        if re.fullmatch(r"[0-9]{1,4}", line):
            continue
        if len(line) <= 1:
            continue
        result.append(line)
    return result


def _looks_like_prakran(line: str) -> bool:
    return bool(_PRAKRAN_PATTERN.search(line)) and len(line) <= 120


def _extract_prakran_from_prefix(line: str) -> tuple[str | None, str]:
    match = _PRAKRAN_NUM_PREFIX.match(line)
    if not match:
        return None, line
    number = int(match.group(1))
    remainder = normalize_text(match.group(2))
    return f"Prakran {number}", remainder


def _extract_prakran_from_keyword(line: str) -> str | None:
    if not _looks_like_prakran(line):
        return None
    number_match = re.search(r"(\d{1,3})", line)
    if number_match:
        return f"Prakran {int(number_match.group(1))}"
    return line


def _extract_chopai_number(line: str) -> str | None:
    match = re.search(r"(\d{1,4})\s*$", line)
    return match.group(1) if match else None


def _looks_like_chopai_marker(line: str) -> bool:
    if len(line) > 220:
        return False
    return bool(_CHOPAI_MARKER_PATTERN.search(line))


def _script_name(style: str) -> str:
    if style == "hi":
        return "devanagari"
    if style == "gu":
        return "gujarati"
    return "latin"


def _build_unit(
    granth: str,
    prakran: str,
    pdf_path: Path,
    source_set: str,
    page_number: int,
    chopai_lines: list[str],
    meaning_lines: list[str],
    chunk_type: str,
) -> ParsedUnit:
    meaning_text = " ".join(line for line in meaning_lines if line)
    if not meaning_text:
        meaning_text = " ".join(chopai_lines)

    combined = "\n".join([*chopai_lines, meaning_text]).strip()
    style = detect_style(combined)
    script_name = _script_name(style)
    normalized = normalize_text(combined)

    translit = transliterate_to_latin(combined).lower()

    return ParsedUnit(
        granth_name=granth,
        prakran_name=prakran,
        chopai_number=_extract_chopai_number(chopai_lines[-1] if chopai_lines else ""),
        prakran_chopai_index=None,
        chopai_lines=chopai_lines,
        meaning_text=meaning_text,
        language_script=script_name,
        page_number=page_number,
        pdf_path=str(pdf_path),
        source_set=source_set,
        normalized_text=normalized,
        translit_hi_latn=translit,
        translit_gu_latn=translit,
        chunk_text=combined,
        chunk_type=chunk_type,
    )


def _parse_page(
    granth: str,
    source_set: str,
    pdf_path: Path,
    page: PageText,
    incoming_prakran: str,
) -> tuple[list[ParsedUnit], str]:
    lines = _clean_lines(page.text)
    if not lines:
        return [], incoming_prakran

    current_prakran = incoming_prakran
    units: list[ParsedUnit] = []

    pending_chopai: list[str] = []
    pending_meaning: list[str] = []

    prev_line = ""

    def flush_current() -> None:
        nonlocal pending_chopai, pending_meaning
        if not pending_chopai and not pending_meaning:
            return
        chopai = pending_chopai[:2] if pending_chopai else [pending_meaning[0]]
        unit = _build_unit(
            granth=granth,
            prakran=current_prakran,
            pdf_path=pdf_path,
            source_set=source_set,
            page_number=page.page_number,
            chopai_lines=chopai,
            meaning_lines=pending_meaning,
            chunk_type="combined",
        )
        units.append(unit)
        pending_chopai = []
        pending_meaning = []

    for line in lines:
        prakran_from_prefix, remainder = _extract_prakran_from_prefix(line)
        if prakran_from_prefix:
            flush_current()
            current_prakran = prakran_from_prefix
            if remainder:
                line = remainder
            else:
                prev_line = line
                continue

        prakran_from_keyword = _extract_prakran_from_keyword(line)
        if prakran_from_keyword:
            flush_current()
            current_prakran = prakran_from_keyword
            prev_line = line
            continue

        if _looks_like_chopai_marker(line):
            flush_current()
            candidate_lines: list[str] = []
            if prev_line and prev_line != current_prakran:
                candidate_lines.append(prev_line)
            candidate_lines.append(line)
            pending_chopai = candidate_lines[-2:]
            prev_line = line
            continue

        if pending_chopai:
            pending_meaning.append(line)
        else:
            pending_meaning.append(line)
        prev_line = line

    flush_current()

    if not units:
        # Fallback chunking for pages that do not match chopai patterns.
        block: list[str] = []
        for line in lines:
            block.append(line)
            if len(block) >= 6:
                unit = _build_unit(
                    granth=granth,
                    prakran=current_prakran,
                    pdf_path=pdf_path,
                    source_set=source_set,
                    page_number=page.page_number,
                    chopai_lines=block[:2],
                    meaning_lines=block[2:],
                    chunk_type="fallback",
                )
                units.append(unit)
                block = []
        if block:
            unit = _build_unit(
                granth=granth,
                prakran=current_prakran,
                pdf_path=pdf_path,
                source_set=source_set,
                page_number=page.page_number,
                chopai_lines=block[:2],
                meaning_lines=block[2:],
                chunk_type="fallback",
            )
            units.append(unit)

    return units, current_prakran
