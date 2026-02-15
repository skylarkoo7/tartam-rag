from app.db import RetrievedUnit
from app.retrieval import reciprocal_rank_fusion


def _unit(idx: int) -> RetrievedUnit:
    return RetrievedUnit(
        id=f"id-{idx}",
        granth_name="Granth",
        prakran_name="Prakran",
        chopai_number=None,
        chopai_lines=["line1", "line2"],
        meaning_text="meaning",
        language_script="devanagari",
        page_number=1,
        pdf_path="/tmp/doc.pdf",
        source_set="hindi-arth",
        normalized_text="text",
        translit_hi_latn="text",
        translit_gu_latn="text",
        chunk_text="text",
        chunk_type="combined",
    )


def test_rrf_prioritizes_shared_candidates() -> None:
    lex = [(_unit(1), 0.9), (_unit(2), 0.8)]
    vec = [(_unit(2), 0.9), (_unit(3), 0.8)]

    fused = reciprocal_rank_fusion(lex, vec)
    ids = [item.unit.id for item in fused]

    assert ids[0] == "id-2"
