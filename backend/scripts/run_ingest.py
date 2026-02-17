from app.config import get_settings
from app.ingestion import IngestionService
from app.db import Database
from app.openai_client import OpenAIClient
from app.vector_store import VectorStore


def main() -> None:
    settings = get_settings()
    db = Database(settings.db_path)
    db.init_db()
    vectors = VectorStore(settings.chroma_path)
    llm = OpenAIClient(
        api_key=settings.openai_api_key,
        chat_model=settings.openai_chat_model,
        embedding_model=settings.openai_embedding_model,
        vision_model=settings.openai_vision_model,
    )

    service = IngestionService(settings=settings, db=db, vectors=vectors, llm=llm)
    stats = service.ingest()

    print("Ingest complete")
    print(f"files_processed={stats.files_processed}")
    print(f"chunks_created={stats.chunks_created}")
    print(f"failed_files={stats.failed_files}")
    print(f"ocr_pages={stats.ocr_pages}")
    if stats.notes:
        print("notes:")
        for note in stats.notes:
            print(f"- {note}")


if __name__ == "__main__":
    main()
