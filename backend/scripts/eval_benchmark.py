from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.chat import ChatService
from app.config import get_settings
from app.db import Database
from app.gemini_client import GeminiClient
from app.models import ChatRequest
from app.retrieval import RetrievalService
from app.vector_store import VectorStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Tartam RAG benchmark from JSONL.")
    parser.add_argument("--input", required=True, help="Path to benchmark JSONL")
    parser.add_argument("--top-k", type=int, default=3, help="Citations to evaluate")
    return parser.parse_args()


def run_eval(input_path: Path, top_k: int) -> None:
    settings = get_settings()
    db = Database(settings.db_path)
    db.init_db()

    vectors = VectorStore(settings.chroma_path)
    gemini = GeminiClient(
        api_key=settings.gemini_api_key,
        chat_model=settings.gemini_chat_model,
        embedding_model=settings.gemini_embedding_model,
    )
    retrieval = RetrievalService(db=db, vectors=vectors, gemini=gemini)
    chat = ChatService(settings=settings, db=db, retrieval=retrieval, gemini=gemini)

    rows = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        print("No benchmark rows found")
        return

    hit_count = 0
    detailed: list[dict] = []

    for idx, row in enumerate(rows, start=1):
        question = row["question"]
        expected_granth = row.get("expected_granth")
        expected_prakran = row.get("expected_prakran")

        response = chat.respond(
            ChatRequest(
                session_id=f"eval_{idx}",
                message=question,
                style_mode="auto",
                top_k=top_k,
            )
        )

        matched = False
        for citation in response.citations[:top_k]:
            granth_ok = expected_granth is None or expected_granth.lower() in citation.granth_name.lower()
            prakran_ok = expected_prakran is None or expected_prakran.lower() in citation.prakran_name.lower()
            if granth_ok and prakran_ok:
                matched = True
                break

        if matched:
            hit_count += 1

        detailed.append(
            {
                "question": question,
                "matched": matched,
                "not_found": response.not_found,
                "top_citations": [
                    {
                        "granth": citation.granth_name,
                        "prakran": citation.prakran_name,
                        "score": citation.score,
                    }
                    for citation in response.citations[:top_k]
                ],
            }
        )

    accuracy = hit_count / len(rows)

    print(f"rows={len(rows)}")
    print(f"top{top_k}_grounded_hit_rate={accuracy:.2%}")
    print(json.dumps({"details": detailed}, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()
    run_eval(input_path=Path(args.input), top_k=args.top_k)


if __name__ == "__main__":
    main()
