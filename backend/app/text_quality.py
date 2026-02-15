from __future__ import annotations

import re

from .language import normalize_text

# Common mojibake markers seen in legacy-font PDF extraction for Indic scripts.
_GARBLED_PATTERN = re.compile(r"[Ÿ¢£¤¥¦§¨©ª«¬®±²³´µ¶·¸¹º»¼½¾¿ÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß]")


def garbled_ratio(text: str) -> float:
    text = text or ""
    if not text:
        return 0.0

    markers = len(_GARBLED_PATTERN.findall(text))
    control = sum(1 for ch in text if ord(ch) < 32 and ch not in "\n\t\r")
    return (markers + control) / max(len(text), 1)


def is_garbled_text(text: str, threshold: float = 0.015) -> bool:
    return garbled_ratio(text) >= threshold


def safe_display_text(text: str, fallback: str) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return fallback
    if is_garbled_text(cleaned):
        return fallback
    return cleaned
