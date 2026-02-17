from pathlib import Path

from app.chat import ChatService
from app.config import Settings
from app.db import Database, RetrievedUnit
from app.fx import FxService
from app.openai_client import OpenAIClient
from app.pricing import PricingCatalog
from app.query_context import QueryContext


def _service(tmp_path: Path) -> ChatService:
    settings = Settings(
        db_path=tmp_path / "app.db",
        data_dir=tmp_path,
        chroma_path=tmp_path / "chroma",
    )
    db = Database(settings.db_path)
    db.init_db()
    llm = OpenAIClient(api_key=None, chat_model="gpt-5.2", embedding_model="text-embedding-3-large", vision_model="gpt-5.2")
    pricing = PricingCatalog(
        version="test",
        source_url="https://example.com",
        rows=[
            {
                "model": "gpt-5.2",
                "endpoint": "responses",
                "input_per_1m_usd": 5.0,
                "cached_input_per_1m_usd": 0.5,
                "output_per_1m_usd": 15.0,
            }
        ],
    )
    fx = FxService(db=db, primary_url="http://127.0.0.1:9", refresh_hours=6, fallback_rate=83.0)
    return ChatService(
        settings=settings,
        db=db,
        retrieval=None,  # type: ignore[arg-type]
        llm=llm,
        pricing_catalog=pricing,
        fx_service=fx,
    )


def _unit() -> RetrievedUnit:
    return RetrievedUnit(
        id="u1",
        granth_name="ShriSingaar",
        prakran_name="Prakran 14",
        prakran_number=14,
        prakran_confidence=0.9,
        chopai_number="62",
        prakran_chopai_index=5,
        chopai_lines=["line one", "line two"],
        meaning_text="meaning",
        language_script="devanagari",
        page_number=15,
        pdf_path="/tmp/x.pdf",
        source_set="hindi-arth",
        normalized_text="text",
        translit_hi_latn="text",
        translit_gu_latn="text",
        chunk_text="text",
        chunk_type="combined",
    )


def _query_context() -> QueryContext:
    return QueryContext(
        intent="general_qa",
        granth_name="ShriSingaar",
        prakran_number=14,
        prakran_range_start=None,
        prakran_range_end=None,
        chopai_number=None,
        requires_summary=False,
        requires_count=False,
        context_carried=False,
        notes=[],
    )


def test_normalize_grounding_removes_bracket_only_artifacts(tmp_path: Path) -> None:
    service = _service(tmp_path)
    text = "Direct Answer: x\nExplanation from Chopai: y\nGrounding: [2]"
    normalized = service._normalize_grounding_line(text, [_unit()], _query_context())  # noqa: SLF001
    assert "[2]" not in normalized
    assert "Grounding: ShriSingaar | Prakran 14 | p.15" in normalized


def test_ensure_structured_answer_adds_required_sections(tmp_path: Path) -> None:
    service = _service(tmp_path)
    text = "Simple plain output without headers."
    structured = service._ensure_structured_answer(text, [_unit()], _query_context())  # noqa: SLF001
    assert "Direct Answer:" in structured
    assert "Explanation from Chopai:" in structured
    assert "Grounding:" in structured
