from app.db import RetrievedUnit
from app.query_context import SessionContextState, parse_query_context, unit_matches_query


def _unit(
    *,
    granth_name: str = "ShriSingaar",
    prakran_name: str = "Prakran 14",
    chopai_number: str | None = "4",
    chunk_text: str = "-14- some text",
) -> RetrievedUnit:
    return RetrievedUnit(
        id="u1",
        granth_name=granth_name,
        prakran_name=prakran_name,
        chopai_number=chopai_number,
        prakran_chopai_index=int(chopai_number) if chopai_number and chopai_number.isdigit() else None,
        chopai_lines=["a", "b"],
        meaning_text="m",
        language_script="devanagari",
        page_number=1,
        pdf_path="/tmp/x.pdf",
        source_set="hindi-arth",
        normalized_text=chunk_text,
        translit_hi_latn=chunk_text,
        translit_gu_latn=chunk_text,
        chunk_text=chunk_text,
        chunk_type="combined",
    )


def test_parse_range_query_with_granth_alias() -> None:
    query = parse_query_context(
        "singar granth prakran 14 to 19 summary and explanation",
        granths=["ShriSingaar", "ShriKirantan"],
        prior=SessionContextState(),
    )
    assert query.granth_name == "ShriSingaar"
    assert query.prakran_range_start == 14
    assert query.prakran_range_end == 19
    assert query.requires_summary


def test_parse_specific_chopai_query() -> None:
    query = parse_query_context(
        "what did chaupai 4 of prakran 14 says",
        granths=["ShriSingaar"],
        prior=SessionContextState(),
    )
    assert query.chopai_number == 4
    assert query.prakran_number == 14
    assert query.intent in {"specific_chopai", "prakran_summary"}


def test_carries_context_when_missing_granth() -> None:
    query = parse_query_context(
        "what did chaupai 4 say?",
        granths=["ShriSingaar"],
        prior=SessionContextState(granth_name="ShriSingaar", prakran_number=14),
    )
    assert query.granth_name == "ShriSingaar"
    assert query.prakran_number == 14


def test_unit_matches_query_constraints() -> None:
    query = parse_query_context(
        "prakran 14 ma chaupai 4 shu che",
        granths=["ShriSingaar"],
        prior=SessionContextState(granth_name="ShriSingaar"),
    )
    assert unit_matches_query(_unit(), query)
    assert not unit_matches_query(_unit(chopai_number="5"), query)


def test_unit_matches_query_with_prakran_relative_index() -> None:
    query = parse_query_context(
        "ShriSingaar prakran 14 chaupai 4",
        granths=["ShriSingaar"],
        prior=SessionContextState(),
    )
    candidate = _unit(chopai_number="62")
    candidate.prakran_chopai_index = 4
    assert unit_matches_query(candidate, query)
