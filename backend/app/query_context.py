from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .db import RetrievedUnit


_PRAKRAN_WORDS = r"(?:prakran|prakaran|प्रकरण|पकरण|પ્રકરણ|પકરણ)"
_CHOPAI_WORDS = r"(?:chopai|chaupai|ચોપાઈ|ચોપાઇ|चौपाई|चोपाई)"

_SUMMARY_HINTS = {
    "summary",
    "summarize",
    "explain",
    "explanation",
    "samjhao",
    "samjhaao",
    "saransh",
    "saar",
    "kya",
    "bataya",
    "shu",
    "kahyu",
    "kahe",
}
_COUNT_HINTS = {
    "count",
    "howmany",
    "kitni",
    "ketli",
    "ketla",
    "number",
}

_FOLLOWUP_HINTS = {
    "usme",
    "isme",
    "tema",
    "ae",
    "te",
    "that",
    "this",
    "same",
    "upar",
    "uparnu",
}


@dataclass(slots=True)
class SessionContextState:
    granth_name: str | None = None
    prakran_number: int | None = None
    prakran_range_start: int | None = None
    prakran_range_end: int | None = None
    chopai_number: int | None = None


@dataclass(slots=True)
class QueryContext:
    intent: str
    granth_name: str | None
    prakran_number: int | None
    prakran_range_start: int | None
    prakran_range_end: int | None
    chopai_number: int | None
    requires_summary: bool
    requires_count: bool
    context_carried: bool
    notes: list[str]

    @property
    def has_prakran_constraint(self) -> bool:
        return self.prakran_number is not None or (
            self.prakran_range_start is not None and self.prakran_range_end is not None
        )

    @property
    def has_reference_constraint(self) -> bool:
        return self.has_prakran_constraint or self.chopai_number is not None or self.granth_name is not None

    def prakran_numbers(self, max_span: int = 20) -> list[int]:
        if self.prakran_number is not None:
            return [self.prakran_number]
        if self.prakran_range_start is None or self.prakran_range_end is None:
            return []

        start = min(self.prakran_range_start, self.prakran_range_end)
        end = max(self.prakran_range_start, self.prakran_range_end)
        if end - start > max_span:
            end = start + max_span
        return list(range(start, end + 1))


def parse_query_context(
    message: str,
    granths: list[str],
    prior: SessionContextState,
    *,
    filter_granth: str | None = None,
    filter_prakran: str | None = None,
) -> QueryContext:
    text = _normalize(message)
    lowered = text.lower()

    detected_granth = _detect_granth(message, granths)
    filter_granth = (filter_granth or "").strip() or None
    granth_name = filter_granth or detected_granth

    prakran_range = _extract_prakran_range(lowered)
    prakran_number = _extract_single_prakran_number(lowered) if not prakran_range else None
    chopai_number = _extract_chopai_number(lowered)

    filter_prakran_number = _extract_first_number(_normalize_digits(filter_prakran or ""))
    if filter_prakran_number is not None and prakran_number is None and prakran_range is None:
        prakran_number = filter_prakran_number

    summary_hint = _has_any_token(lowered, _SUMMARY_HINTS) or bool(prakran_range)
    count_hint = _has_any_token(lowered, _COUNT_HINTS) and bool(re.search(_CHOPAI_WORDS, lowered))
    asks_chopai = bool(re.search(_CHOPAI_WORDS, lowered))
    asks_prakran = bool(re.search(_PRAKRAN_WORDS, lowered))

    intent = "general_qa"
    if count_hint:
        intent = "count_chopai"
    elif chopai_number is not None and (asks_chopai or asks_prakran):
        intent = "specific_chopai"
    elif prakran_range:
        intent = "prakran_range_summary"
    elif prakran_number is not None and summary_hint:
        intent = "prakran_summary"

    carried = False
    should_carry = _should_carry_context(lowered, asks_prakran, asks_chopai)
    if should_carry:
        if granth_name is None and prior.granth_name:
            granth_name = prior.granth_name
            carried = True
        if prakran_number is None and prakran_range is None and prior.prakran_number is not None:
            prakran_number = prior.prakran_number
            carried = True
        if prakran_range is None and prior.prakran_range_start is not None and prior.prakran_range_end is not None:
            if asks_prakran and _mentions_followup(lowered):
                prakran_range = (prior.prakran_range_start, prior.prakran_range_end)
                carried = True

    notes: list[str] = []
    if carried:
        notes.append("Used previous conversation context for missing references.")
    if filter_granth:
        notes.append(f"Applied granth filter: {filter_granth}.")
    if filter_prakran:
        notes.append(f"Applied prakran filter: {filter_prakran}.")

    return QueryContext(
        intent=intent,
        granth_name=granth_name,
        prakran_number=prakran_number,
        prakran_range_start=prakran_range[0] if prakran_range else None,
        prakran_range_end=prakran_range[1] if prakran_range else None,
        chopai_number=chopai_number,
        requires_summary=summary_hint or intent in {"prakran_summary", "prakran_range_summary"},
        requires_count=count_hint,
        context_carried=carried,
        notes=notes,
    )


def next_session_context(prior: SessionContextState, current: QueryContext) -> SessionContextState:
    return SessionContextState(
        granth_name=current.granth_name or prior.granth_name,
        prakran_number=current.prakran_number if current.prakran_number is not None else prior.prakran_number,
        prakran_range_start=(
            current.prakran_range_start if current.prakran_range_start is not None else prior.prakran_range_start
        ),
        prakran_range_end=current.prakran_range_end if current.prakran_range_end is not None else prior.prakran_range_end,
        chopai_number=current.chopai_number if current.chopai_number is not None else prior.chopai_number,
    )


def build_query_hints(query: QueryContext) -> list[str]:
    hints: list[str] = []
    if query.granth_name:
        hints.append(query.granth_name)
    if query.prakran_number is not None:
        number = str(query.prakran_number)
        hints.extend([f"prakran {number}", f"प्रकरण {number}", f"પ્રકરણ {number}", f"-{number}-"])
    if query.prakran_range_start is not None and query.prakran_range_end is not None:
        for number in query.prakran_numbers(max_span=8):
            hints.extend([f"prakran {number}", f"-{number}-"])
    if query.chopai_number is not None:
        number = str(query.chopai_number)
        hints.extend([f"chopai {number}", f"chaupai {number}", f"चौपाई {number}", f"ચોપાઈ {number}"])

    deduped: list[str] = []
    seen: set[str] = set()
    for hint in hints:
        clean = hint.strip()
        key = clean.lower()
        if not clean or key in seen:
            continue
        seen.add(key)
        deduped.append(clean)
    return deduped[:10]


def unit_matches_query(unit: RetrievedUnit, query: QueryContext) -> bool:
    if query.granth_name and unit.granth_name != query.granth_name:
        return False

    if query.chopai_number is not None:
        parsed = _extract_first_number(_normalize_digits(unit.chopai_number or ""))
        prakran_idx = unit.prakran_chopai_index
        if parsed != query.chopai_number and prakran_idx != query.chopai_number:
            return False

    prakran_numbers = query.prakran_numbers(max_span=20)
    if prakran_numbers:
        if not any(unit_matches_prakran(unit, number) for number in prakran_numbers):
            return False

    return True


def unit_matches_prakran(unit: RetrievedUnit, prakran_number: int) -> bool:
    target = str(prakran_number)
    prakran_name = (unit.prakran_name or "").strip().lower()
    explicit_name_match = re.search(r"^prakran\s+(\d{1,3})$", prakran_name)
    if explicit_name_match:
        return int(explicit_name_match.group(1)) == prakran_number

    candidate_text = " ".join(
        [
            _normalize_digits(unit.prakran_name),
            _normalize_digits(unit.chunk_text[:900]),
            _normalize_digits(unit.normalized_text[:900]),
        ]
    ).lower()

    if not candidate_text:
        return False

    explicit_patterns = [
        rf"(?<!\d){re.escape(target)}(?!\d)",
        rf"-{re.escape(target)}-",
        rf"{re.escape(target)}\)",
        rf"\({re.escape(target)}",
    ]
    return any(re.search(pattern, candidate_text) for pattern in explicit_patterns)


def parse_session_context(row: dict | None) -> SessionContextState:
    if not row:
        return SessionContextState()

    return SessionContextState(
        granth_name=(row.get("granth_name") or None),
        prakran_number=_coerce_int(row.get("prakran_number")),
        prakran_range_start=_coerce_int(row.get("prakran_range_start")),
        prakran_range_end=_coerce_int(row.get("prakran_range_end")),
        chopai_number=_coerce_int(row.get("chopai_number")),
    )


def _detect_granth(text: str, granths: list[str]) -> str | None:
    if not granths:
        return None

    flat = _norm_key(text)
    if not flat:
        return None

    candidates: list[tuple[int, str]] = []
    for granth in granths:
        aliases = _granth_aliases(granth)
        for alias in aliases:
            if alias and alias in flat:
                candidates.append((len(alias), granth))
                break

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _granth_aliases(granth: str) -> set[str]:
    raw = granth.strip()
    key = _norm_key(raw)
    aliases = {key}

    de_camel = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw)
    aliases.add(_norm_key(de_camel))

    base = key.replace("shri", "").replace("sri", "")
    aliases.add(base)
    aliases.add(base.replace("aa", "a"))

    extra: dict[str, list[str]] = {
        "singaar": [
            "singar",
            "sringar",
            "shringar",
            "श्रृंगार",
            "शृंगार",
            "सिंगार",
            "श्रीसिंगार",
            "श्री सिंगार",
            "સિંગાર",
            "શૃંગાર",
        ],
        "kirantan": ["kirtan", "kiratan", "कीर्तन", "કીર્તન"],
        "prakash": ["prkash", "prakas", "प्रकाश", "પ્રકાશ"],
        "ras": ["raas", "ras", "रास", "રાસ"],
    }
    for token, values in extra.items():
        if token in key:
            aliases.update(_norm_key(item) for item in values)

    return {item for item in aliases if item}


def _extract_prakran_range(text: str) -> tuple[int, int] | None:
    pattern = re.compile(
        rf"{_PRAKRAN_WORDS}\s*(\d{{1,3}})\s*(?:to|se|thi|થી|से|[-–—])\s*(\d{{1,3}})",
        re.IGNORECASE,
    )
    match = pattern.search(_normalize_digits(text))
    if match:
        return int(match.group(1)), int(match.group(2))

    reverse_pattern = re.compile(
        rf"(\d{{1,3}})\s*(?:to|se|thi|થી|से|[-–—])\s*(\d{{1,3}})\s*{_PRAKRAN_WORDS}",
        re.IGNORECASE,
    )
    match = reverse_pattern.search(_normalize_digits(text))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _extract_single_prakran_number(text: str) -> int | None:
    pattern = re.compile(rf"{_PRAKRAN_WORDS}\s*(\d{{1,3}})", re.IGNORECASE)
    match = pattern.search(_normalize_digits(text))
    if not match:
        return None
    return int(match.group(1))


def _extract_chopai_number(text: str) -> int | None:
    source = _normalize_digits(text)
    direct = re.search(rf"{_CHOPAI_WORDS}\s*(\d{{1,4}})", source, flags=re.IGNORECASE)
    if direct:
        return int(direct.group(1))

    reverse = re.search(rf"(\d{{1,4}})\s*(?:th|st|nd|rd)?\s*{_CHOPAI_WORDS}", source, flags=re.IGNORECASE)
    if reverse:
        return int(reverse.group(1))
    return None


def _should_carry_context(text: str, asks_prakran: bool, asks_chopai: bool) -> bool:
    if asks_prakran or asks_chopai:
        return True
    if _mentions_followup(text):
        return True
    return False


def _mentions_followup(text: str) -> bool:
    normalized = _norm_key(text)
    return any(token in normalized for token in _FOLLOWUP_HINTS)


def _has_any_token(text: str, terms: set[str]) -> bool:
    tokenized = _norm_key(text)
    return any(item in tokenized for item in terms)


def _normalize_digits(text: str) -> str:
    if not text:
        return ""

    dev = "०१२३४५६७८९"
    guj = "૦૧૨૩૪૫૬૭૮૯"
    translation = {ord(ch): str(idx) for idx, ch in enumerate(dev)}
    translation.update({ord(ch): str(idx) for idx, ch in enumerate(guj)})
    return text.translate(translation)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").strip()


def _norm_key(text: str) -> str:
    text = _normalize_digits(_normalize(text)).lower()
    return re.sub(r"[^a-z0-9\u0900-\u097f\u0a80-\u0aff]+", "", text)


def _extract_first_number(text: str) -> int | None:
    match = re.search(r"(\d{1,4})", text or "")
    if not match:
        return None
    return int(match.group(1))


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None
