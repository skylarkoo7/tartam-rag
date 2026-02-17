from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Settings:
    app_name: str = "Tartam RAG API"
    env: str = "local"
    api_prefix: str = "/api"

    workspace_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    data_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1] / "data")
    db_path: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1] / "data" / "app.db")
    chroma_path: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1] / "data" / "chroma")

    corpus_dirs: list[str] = field(
        default_factory=lambda: [
            "tartam/Shri Tartamsagar  (hindi-arth)",
            "tartam/Shri Tartamsagar (guj-arth)",
        ]
    )

    gemini_api_key: str | None = None
    gemini_chat_model: str = "gemini-3-flash-preview"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_ocr_models: list[str] = field(
        default_factory=lambda: ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-3-flash-preview"]
    )
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4o-mini"
    llm_provider: str = "auto"

    retrieval_top_k: int = 6
    minimum_grounding_score: float = 0.015
    request_rate_limit_per_min: int = 40

    allow_debug_payloads: bool = True
    enable_ocr_fallback: bool = True
    ocr_quality_threshold: float = 0.22
    ocr_force_on_garbled: bool = True
    ingest_gemini_ocr_max_pages: int = 200
    allow_gemini_page_ocr_recovery: bool = True

    @property
    def corpus_paths(self) -> list[Path]:
        paths: list[Path] = []
        for item in self.corpus_dirs:
            path = Path(item)
            if not path.is_absolute():
                path = self.workspace_root / path
            paths.append(path)
        return paths


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _to_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _split_csv(value: str | None, default: list[str]) -> list[str]:
    if value is None:
        return default
    result = [item.strip() for item in value.split(",") if item.strip()]
    return result or default


def _load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_settings() -> Settings:
    workspace = Path(__file__).resolve().parents[2]
    env_candidates = [workspace / "backend" / ".env", workspace / ".env"]
    for candidate in env_candidates:
        _load_dotenv_file(candidate)

    settings = Settings()

    settings.app_name = os.getenv("APP_NAME", settings.app_name)
    settings.env = os.getenv("ENV", settings.env)
    settings.api_prefix = os.getenv("API_PREFIX", settings.api_prefix)

    settings.gemini_api_key = os.getenv("GEMINI_API_KEY", settings.gemini_api_key)
    settings.gemini_chat_model = os.getenv("GEMINI_CHAT_MODEL", settings.gemini_chat_model)
    settings.gemini_embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", settings.gemini_embedding_model)
    settings.gemini_ocr_models = _split_csv(os.getenv("GEMINI_OCR_MODELS"), settings.gemini_ocr_models)
    settings.openai_api_key = os.getenv("OPENAI_API_KEY", settings.openai_api_key)
    settings.openai_chat_model = os.getenv("OPENAI_CHAT_MODEL", settings.openai_chat_model)
    settings.llm_provider = os.getenv("LLM_PROVIDER", settings.llm_provider).strip().lower()

    settings.corpus_dirs = _split_csv(os.getenv("CORPUS_DIRS"), settings.corpus_dirs)

    settings.retrieval_top_k = _to_int(os.getenv("RETRIEVAL_TOP_K"), settings.retrieval_top_k)
    settings.minimum_grounding_score = _to_float(
        os.getenv("MINIMUM_GROUNDING_SCORE"), settings.minimum_grounding_score
    )
    settings.request_rate_limit_per_min = _to_int(
        os.getenv("REQUEST_RATE_LIMIT_PER_MIN"), settings.request_rate_limit_per_min
    )

    settings.allow_debug_payloads = _to_bool(os.getenv("ALLOW_DEBUG_PAYLOADS"), settings.allow_debug_payloads)
    settings.enable_ocr_fallback = _to_bool(os.getenv("ENABLE_OCR_FALLBACK"), settings.enable_ocr_fallback)
    settings.ocr_quality_threshold = _to_float(os.getenv("OCR_QUALITY_THRESHOLD"), settings.ocr_quality_threshold)
    settings.ocr_force_on_garbled = _to_bool(os.getenv("OCR_FORCE_ON_GARBLED"), settings.ocr_force_on_garbled)
    settings.ingest_gemini_ocr_max_pages = _to_int(
        os.getenv("INGEST_GEMINI_OCR_MAX_PAGES"), settings.ingest_gemini_ocr_max_pages
    )
    settings.allow_gemini_page_ocr_recovery = _to_bool(
        os.getenv("ALLOW_GEMINI_PAGE_OCR_RECOVERY"), settings.allow_gemini_page_ocr_recovery
    )

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)

    return settings
