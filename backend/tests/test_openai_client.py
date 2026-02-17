from app.db import RetrievedUnit
from app.openai_client import OpenAIClient


def _unit() -> RetrievedUnit:
    return RetrievedUnit(
        id="u1",
        granth_name="Shri Ras",
        prakran_name="Prakran A",
        prakran_number=1,
        prakran_confidence=0.9,
        chopai_number="1",
        prakran_chopai_index=1,
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


def test_generate_answer_without_key_returns_not_found_template() -> None:
    client = OpenAIClient(api_key=None, chat_model="x", embedding_model="y", vision_model="z")
    result = client.generate_answer(
        question="what does this teach",
        citations=[_unit()],
        target_style="en",
        conversation_context=[{"role": "user", "text": "hello"}],
    )

    assert "I could not find this clearly" in result


def test_plan_query_without_key_returns_default() -> None:
    client = OpenAIClient(api_key=None, chat_model="x", embedding_model="y", vision_model="z")
    plan = client.plan_query("what does this teach", conversation_context=[])
    assert plan["intent"] == "answer_user_question_from_scripture"
    assert isinstance(plan["sub_queries"], list)


def test_summarize_memory_without_key_returns_fallback() -> None:
    client = OpenAIClient(api_key=None, chat_model="x", embedding_model="y", vision_model="z")
    summary, key_facts = client.summarize_memory(
        existing_summary="Earlier discussion about devotion.",
        existing_key_facts=["User prefers Hinglish responses."],
        latest_user_message="explain this chopai in simple words",
        latest_assistant_message="This teaches surrender with steady remembrance.",
        conversation_context=[{"role": "user", "text": "previous"}],
        citations=[_unit()],
    )

    assert "devotion" in summary.lower() or "explain this chopai" in summary.lower()
    assert key_facts


def test_embed_fallback_produces_nonempty_vector() -> None:
    client = OpenAIClient(api_key=None, chat_model="x", embedding_model="y", vision_model="z")
    vector = client.embed("prakran 14 chaupai 4")

    assert len(vector) > 0
    assert any(value != 0 for value in vector)
