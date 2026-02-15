from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

try:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate
except Exception:  # pragma: no cover - optional dependency behavior
    sanscript = None
    transliterate = None

StyleTag = Literal["hi", "gu", "en", "hi_latn", "gu_latn"]

_HI_HINTS = {
    "kaise",
    "kya",
    "kyu",
    "nahi",
    "hai",
    "aap",
    "tum",
    "bhagwan",
    "prarthana",
}
_GU_HINTS = {
    "kem",
    "cho",
    "shu",
    "tame",
    "hu",
    "bhagvan",
    "chhe",
    "mara",
}


@dataclass(slots=True)
class ScriptCounts:
    devanagari: int = 0
    gujarati: int = 0
    latin: int = 0


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _count_scripts(text: str) -> ScriptCounts:
    counts = ScriptCounts()
    for ch in text:
        code = ord(ch)
        if 0x0900 <= code <= 0x097F:
            counts.devanagari += 1
        elif 0x0A80 <= code <= 0x0AFF:
            counts.gujarati += 1
        elif (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A):
            counts.latin += 1
    return counts


def _latin_style_guess(text: str) -> StyleTag:
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    hi_score = len(words & _HI_HINTS)
    gu_score = len(words & _GU_HINTS)

    if gu_score > hi_score and gu_score > 0:
        return "gu_latn"
    if hi_score > 0:
        return "hi_latn"
    return "en"


def detect_style(text: str) -> StyleTag:
    text = normalize_text(text)
    counts = _count_scripts(text)

    if counts.devanagari > counts.gujarati and counts.devanagari >= counts.latin:
        return "hi"
    if counts.gujarati > counts.devanagari and counts.gujarati >= counts.latin:
        return "gu"
    return _latin_style_guess(text)


def transliterate_to_latin(text: str) -> str:
    text = normalize_text(text)
    if not text:
        return ""

    if transliterate is None or sanscript is None:
        return text

    counts = _count_scripts(text)
    try:
        if counts.devanagari > 0:
            return transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
        if counts.gujarati > 0:
            return transliterate(text, sanscript.GUJARATI, sanscript.ITRANS)
    except Exception:
        return text
    return text


def transliterate_latin_to_script(text: str, target: StyleTag) -> str:
    """Best-effort conversion for ITRANS-like user text.

    Roman colloquial phrases are often not strict transliteration. If conversion fails,
    the input is returned unchanged.
    """

    text = normalize_text(text)
    if not text or transliterate is None or sanscript is None:
        return text

    try:
        if target == "hi":
            return transliterate(text, sanscript.ITRANS, sanscript.DEVANAGARI)
        if target == "gu":
            return transliterate(text, sanscript.ITRANS, sanscript.GUJARATI)
    except Exception:
        return text
    return text


def query_variants(query: str, style: StyleTag) -> list[str]:
    normalized = normalize_text(query)
    if not normalized:
        return []

    variants = {normalized, normalized.lower()}
    latin = transliterate_to_latin(normalized)
    if latin:
        variants.add(latin)
        variants.add(latin.lower())

    if style in {"hi_latn", "en"}:
        variants.add(transliterate_latin_to_script(normalized, "hi"))
    if style in {"gu_latn", "en"}:
        variants.add(transliterate_latin_to_script(normalized, "gu"))

    return [item for item in variants if item]


def resolve_output_style(style_mode: str, detected: StyleTag) -> StyleTag:
    if style_mode == "auto":
        return detected
    return style_mode  # type: ignore[return-value]


def render_in_style(text: str, style: StyleTag) -> str:
    """Render output in requested style with best-effort transliteration."""

    if style in {"en", "hi_latn", "gu_latn"}:
        return transliterate_to_latin(text)
    if style == "hi":
        return transliterate_latin_to_script(text, "hi")
    if style == "gu":
        return transliterate_latin_to_script(text, "gu")
    return text
