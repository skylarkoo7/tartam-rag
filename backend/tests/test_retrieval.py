from app.db import RetrievedUnit
from app.retrieval import readability_multiplier, reciprocal_rank_fusion


def _unit(idx: int) -> RetrievedUnit:
    return RetrievedUnit(
        id=f"id-{idx}",
        granth_name="Granth",
        prakran_name="Prakran",
        prakran_number=None,
        prakran_confidence=None,
        chopai_number=None,
        prakran_chopai_index=None,
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


def test_readability_multiplier_penalizes_garbled_text() -> None:
    clean = _unit(10)
    garbled = _unit(11)
    garbled.chunk_text = "Ÿ¢£¤¥¦§¨©ª«¬®±²³´µ¶·¸¹º»¼½¾¿"

    assert readability_multiplier(clean) > readability_multiplier(garbled)
