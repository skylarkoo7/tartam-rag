from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .chat import ChatService
from .config import Settings, get_settings
from .db import Database
from .gemini_client import GeminiClient
from .ingestion import IngestionService
from .language import convert_text_fallback
from .models import (
    ChatRequest,
    ChatResponse,
    ConvertRequest,
    ConvertResponse,
    FiltersResponse,
    HealthResponse,
    IngestResponse,
    MessageRecord,
    SessionRecord,
)
from .rate_limit import InMemoryRateLimiter
from .retrieval import RetrievalService
from .vector_store import VectorStore


def build_services(settings: Settings) -> tuple[Database, VectorStore, GeminiClient, IngestionService, ChatService]:
    db = Database(settings.db_path)
    db.init_db()

    vectors = VectorStore(settings.chroma_path)
    gemini = GeminiClient(
        api_key=settings.gemini_api_key,
        chat_model=settings.gemini_chat_model,
        embedding_model=settings.gemini_embedding_model,
        ocr_models=settings.gemini_ocr_models,
    )

    ingest = IngestionService(settings=settings, db=db, vectors=vectors, gemini=gemini)
    retrieval = RetrievalService(db=db, vectors=vectors, gemini=gemini)
    chat = ChatService(settings=settings, db=db, retrieval=retrieval, gemini=gemini)
    return db, vectors, gemini, ingest, chat


settings = get_settings()
database, vectors, gemini_client, ingestion_service, chat_service = build_services(settings)
rate_limiter = InMemoryRateLimiter(max_per_minute=settings.request_rate_limit_per_min)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "ok"}


@app.get(f"{settings.api_prefix}/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        db_ready=True,
        vector_ready=vectors.available,
        indexed_chunks=database.count_units(),
        llm_enabled=gemini_client.enabled,
        llm_generation_error=_compact_error(gemini_client.last_generation_error),
        ocr_error=_compact_error(gemini_client.last_ocr_error),
    )


@app.post(f"{settings.api_prefix}/ingest", response_model=IngestResponse)
def ingest() -> IngestResponse:
    stats = ingestion_service.ingest()
    return IngestResponse(
        files_processed=stats.files_processed,
        chunks_created=stats.chunks_created,
        failed_files=stats.failed_files,
        ocr_pages=stats.ocr_pages,
        notes=stats.notes or [],
    )


@app.get(f"{settings.api_prefix}/filters", response_model=FiltersResponse)
def filters() -> FiltersResponse:
    granths, prakrans = database.list_filters()
    return FiltersResponse(granths=granths, prakrans=prakrans)


@app.get(f"{settings.api_prefix}/history/{{session_id}}", response_model=list[MessageRecord])
def history(session_id: str) -> list[MessageRecord]:
    rows = database.get_session_messages(session_id)
    return [MessageRecord(**row) for row in rows]


@app.get(f"{settings.api_prefix}/sessions", response_model=list[SessionRecord])
def sessions(limit: int = 50) -> list[SessionRecord]:
    rows = database.list_sessions(limit=limit)
    return [
        SessionRecord(
            session_id=row["session_id"],
            title=(row.get("title_text") or "New chat")[:120],
            preview=(row.get("preview_text") or "")[:240],
            last_message_at=row["last_message_at"],
            message_count=int(row.get("message_count", 0)),
        )
        for row in rows
    ]


@app.post(
    f"{settings.api_prefix}/chat",
    response_model=ChatResponse,
    dependencies=[Depends(rate_limiter.dependency())],
)
def chat(payload: ChatRequest) -> ChatResponse:
    return chat_service.respond(payload)


@app.post(
    f"{settings.api_prefix}/convert",
    response_model=ConvertResponse,
    dependencies=[Depends(rate_limiter.dependency())],
)
def convert(payload: ConvertRequest) -> ConvertResponse:
    if gemini_client.enabled:
        text = gemini_client.convert_text(payload.text, payload.target_mode)
        if text.strip() == payload.text.strip():
            text = convert_text_fallback(payload.text, payload.target_mode)
    else:
        text = convert_text_fallback(payload.text, payload.target_mode)
    return ConvertResponse(text=text, target_mode=payload.target_mode)


@app.get(f"{settings.api_prefix}/pdf/{{citation_id}}")
def citation_pdf(citation_id: str) -> FileResponse:
    unit = database.get_unit_by_id(citation_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Citation not found")

    pdf_path = Path(unit.pdf_path).resolve()
    workspace_root = settings.workspace_root.resolve()
    if workspace_root not in pdf_path.parents and pdf_path != workspace_root:
        raise HTTPException(status_code=403, detail="PDF path is outside workspace")
    if not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="PDF file missing on disk")

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        headers={"Content-Disposition": f'inline; filename="{pdf_path.name}"'},
    )


def _compact_error(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    lowered = text.lower()
    if "resource_exhausted" in lowered or "quota exceeded" in lowered:
        return "Gemini quota exhausted (free-tier limit hit)."
    if "nodename nor servname provided" in lowered or "name resolution" in lowered:
        return "Network/DNS issue while contacting Gemini."
    if "api key" in lowered or "permission" in lowered or "unauthorized" in lowered:
        return "Gemini authentication/permissions issue."
    return text[:180]
