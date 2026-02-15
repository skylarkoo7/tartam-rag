from __future__ import annotations

from pathlib import Path

from app.db import Database


def test_session_memory_round_trip(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    db.init_db()

    db.upsert_session_memory(
        session_id="s1",
        summary_text="User is asking about surrender themes.",
        key_facts=["Prefers Hindi (Roman)", "Discussed ShriKirtan"],
    )

    memory = db.get_session_memory("s1")
    assert memory is not None
    assert memory["summary_text"].startswith("User is asking")
    assert len(memory["key_facts"]) == 2


def test_list_sessions_includes_latest_preview(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    db.init_db()

    db.add_message(
        message_id="m1",
        session_id="sA",
        role="user",
        text="first question",
        style_tag="auto",
        citations_json=None,
    )
    db.add_message(
        message_id="m2",
        session_id="sA",
        role="assistant",
        text="first answer",
        style_tag="en",
        citations_json=None,
    )
    db.add_message(
        message_id="m3",
        session_id="sB",
        role="user",
        text="second session question",
        style_tag="hi_latn",
        citations_json=None,
    )

    sessions = db.list_sessions(limit=10)
    assert len(sessions) == 2

    by_id = {item["session_id"]: item for item in sessions}
    assert by_id["sA"]["title_text"] == "first question"
    assert by_id["sA"]["preview_text"] == "first answer"
    assert by_id["sA"]["message_count"] == 2
