from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


StyleMode = Literal["auto", "hi", "gu", "en", "hi_latn", "gu_latn"]
ConvertMode = Literal["hi", "gu", "en", "hi_latn", "gu_latn", "en_deva", "en_gu"]


class ChatFilters(BaseModel):
    granth: str | None = None
    prakran: str | None = None


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=2, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    style_mode: StyleMode = "auto"
    filters: ChatFilters | None = None
    top_k: int | None = Field(default=None, ge=1, le=12)


class Citation(BaseModel):
    citation_id: str
    granth_name: str
    prakran_name: str
    chopai_number: str | None = None
    prakran_chopai_index: int | None = None
    chopai_lines: list[str]
    meaning_text: str
    page_number: int
    pdf_path: str
    score: float
    prev_context: str | None = None
    next_context: str | None = None


UsageStage = Literal["plan_query", "query_embedding", "generate_answer", "summarize_memory", "convert_answer", "ocr_recovery"]


class UsageLineItem(BaseModel):
    stage: UsageStage
    provider: str
    model: str
    endpoint: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    usd_cost: float = 0.0
    inr_cost: float = 0.0
    pricing_version: str
    fx_rate: float


class CostSummary(BaseModel):
    total_usd: float = 0.0
    total_inr: float = 0.0
    currency_local: str = "INR"
    fx_rate: float = 0.0
    fx_source: str = "fallback"
    line_items: list[UsageLineItem] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    answer_style: StyleMode | str
    not_found: bool
    follow_up_question: str | None = None
    citations: list[Citation]
    cost_summary: CostSummary | None = None
    context_state: dict | None = None
    available_conversions: list[ConvertMode] = Field(
        default_factory=lambda: ["en", "hi", "gu", "hi_latn", "gu_latn", "en_deva", "en_gu"]
    )
    debug: dict | None = None


class ConvertRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12_000)
    target_mode: ConvertMode


class ConvertResponse(BaseModel):
    text: str
    target_mode: ConvertMode


class FiltersResponse(BaseModel):
    granths: list[str]
    prakrans: list[str]


class MessageRecord(BaseModel):
    message_id: str
    session_id: str
    role: Literal["user", "assistant"]
    text: str
    style_tag: str
    citations_json: str | None = None
    cost_json: str | None = None
    created_at: datetime


class SessionRecord(BaseModel):
    session_id: str
    title: str
    preview: str
    last_message_at: datetime
    message_count: int


class ThreadCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class ThreadCreateResponse(BaseModel):
    session_id: str


class SessionCostResponse(BaseModel):
    session_id: str
    turns: int
    total_usd: float
    total_inr: float
    fx_rate: float
    fx_source: str
    by_model: dict[str, dict[str, float]]
    items: list[CostSummary]


class IngestResponse(BaseModel):
    files_processed: int
    chunks_created: int
    failed_files: int
    ocr_pages: int
    notes: list[str]


class HealthResponse(BaseModel):
    status: str
    db_ready: bool
    vector_ready: bool
    indexed_chunks: int
    llm_enabled: bool = False
    llm_provider: str | None = None
    llm_generation_error: str | None = None
    ocr_error: str | None = None
