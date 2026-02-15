from app.db import RetrievedUnit
from app.gemini_client import GeminiClient


def _unit() -> RetrievedUnit:
    return RetrievedUnit(
        id="u1",
        granth_name="Shri Ras",
        prakran_name="Prakran A",
        chopai_number="1",
        chopai_lines=["line 1", "line 2"],
        meaning_text="The teaching says to remain steady and devoted.",
        language_script="devanagari",
        page_number=1,
        pdf_path="/tmp/x.pdf",
        source_set="hindi-arth",
        normalized_text="",
        translit_hi_latn="",
        translit_gu_latn="",
        chunk_text="",
        chunk_type="combined",
    )


def test_fallback_explanation_has_structure() -> None:
    client = GeminiClient(api_key=None, chat_model="x", embedding_model="y")
    result = client.generate_answer(
        question="what does this teach",
        citations=[_unit()],
        target_style="en",
        conversation_context=[{"role": "user", "text": "hello"}],
    )

    assert "Direct Answer:" in result
    assert "Explanation from Chopai:" in result
    assert "Grounding:" in result
