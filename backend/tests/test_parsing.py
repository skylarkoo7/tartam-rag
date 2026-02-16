from pathlib import Path

from app.parsing import parse_pdf_to_units
from app.pdf_extract import PageText


def test_parse_prakran_from_dash_number_heading() -> None:
    pages = [
        PageText(
            page_number=1,
            extraction_method="pdf",
            quality_score=0.8,
            text="\n".join(
                [
                    "-14-",
                    "sample chopai line one",
                    "sample chopai line two JJ 62",
                    "meaning line here",
                ]
            ),
        )
    ]

    units = parse_pdf_to_units(Path("/tmp/13ShriSingaar.pdf"), pages)
    assert units
    assert all(unit.prakran_name == "Prakran 14" for unit in units)


def test_parse_prakran_from_inline_dash_prefix() -> None:
    pages = [
        PageText(
            page_number=1,
            extraction_method="pdf",
            quality_score=0.8,
            text="\n".join(
                [
                    "-19-inline text start",
                    "another line",
                    "line ending JJ 21",
                    "meaning block",
                ]
            ),
        )
    ]
    units = parse_pdf_to_units(Path("/tmp/13ShriSingaar.pdf"), pages)
    assert units
    assert units[0].prakran_name == "Prakran 19"
