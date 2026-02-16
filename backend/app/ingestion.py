from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .db import Database
from .gemini_client import GeminiClient
from .language import normalize_text
from .parsing import ParsedUnit, parse_pdf_to_units
from .pdf_extract import PDFExtractionError, PageText, extract_pdf_pages
from .text_quality import is_garbled_text, likely_misencoded_indic_text
from .vector_store import VectorStore


@dataclass(slots=True)
class IngestStats:
    files_processed: int = 0
    chunks_created: int = 0
    failed_files: int = 0
    ocr_pages: int = 0
    notes: list[str] | None = None

    def __post_init__(self) -> None:
        if self.notes is None:
            self.notes = []


class IngestionService:
    def __init__(self, settings: Settings, db: Database, vectors: VectorStore, gemini: GeminiClient):
        self.settings = settings
        self.db = db
        self.vectors = vectors
        self.gemini = gemini

    def ingest(self) -> IngestStats:
        stats = IngestStats()
        run_id = str(uuid.uuid4())

        self.db.clear_ingested_content()
        if self.vectors.available:
            self.vectors.clear()

        all_records: list[dict] = []
        vector_ids: list[str] = []
        vector_docs: list[str] = []
        vector_metas: list[dict] = []

        corpus_files = self._collect_corpus_files()
        for pdf_path in corpus_files:
            try:
                pages, ocr_count = extract_pdf_pages(
                    pdf_path,
                    enable_ocr_fallback=self.settings.enable_ocr_fallback,
                    ocr_quality_threshold=self.settings.ocr_quality_threshold,
                    force_on_garbled=self.settings.ocr_force_on_garbled,
                )

                gemini_ocr_count = 0
                if self.settings.enable_ocr_fallback and self.settings.allow_gemini_page_ocr_recovery:
                    remaining_ocr_budget = max(0, self.settings.ingest_gemini_ocr_max_pages - stats.ocr_pages)
                    if remaining_ocr_budget > 0:
                        pages, gemini_ocr_count = self._recover_pages_with_gemini(
                            pdf_path=pdf_path,
                            pages=pages,
                            budget=remaining_ocr_budget,
                        )

                stats.ocr_pages += ocr_count + gemini_ocr_count
                units = parse_pdf_to_units(pdf_path, pages)
                normalized_units = self._normalize_units(units)
                all_records.extend(normalized_units)

                stats.files_processed += 1
            except PDFExtractionError as exc:
                stats.failed_files += 1
                stats.notes.append(str(exc))
            except Exception as exc:
                stats.failed_files += 1
                stats.notes.append(f"Failed {pdf_path}: {exc}")

        if all_records:
            self.db.upsert_units(all_records)
            stats.chunks_created = len(all_records)

            if self.vectors.available:
                for record in all_records:
                    vector_ids.append(record["id"])
                    vector_docs.append(record["chunk_text"])
                    vector_metas.append(
                        {
                            "granth_name": record["granth_name"],
                            "prakran_name": record["prakran_name"],
                            "source_set": record["source_set"],
                            "chunk_type": record["chunk_type"],
                        }
                    )
                embeddings = self.gemini.embed_many(vector_docs)
                self.vectors.upsert(
                    ids=vector_ids,
                    texts=vector_docs,
                    embeddings=embeddings,
                    metadatas=vector_metas,
                )
        else:
            stats.notes.append("No chunks were generated. Verify PDF text extraction and parser heuristics.")

        self.db.record_ingest_run(
            run_id=run_id,
            files_processed=stats.files_processed,
            chunks_created=stats.chunks_created,
            failed_files=stats.failed_files,
            ocr_pages=stats.ocr_pages,
            notes=stats.notes,
        )

        return stats

    def _collect_corpus_files(self) -> list[Path]:
        files: list[Path] = []
        for corpus_dir in self.settings.corpus_paths:
            if not corpus_dir.exists():
                continue
            files.extend(sorted(corpus_dir.glob("*.pdf")))
        return files

    def _normalize_units(self, units: list[ParsedUnit]) -> list[dict]:
        records: list[dict] = []
        for idx, unit in enumerate(units):
            stable_input = (
                f"{unit.pdf_path}|{unit.page_number}|{idx}|{unit.prakran_name}|{unit.chunk_text[:200]}"
            )
            item_id = str(uuid.uuid5(uuid.NAMESPACE_URL, stable_input))

            records.append(
                {
                    "id": item_id,
                    "granth_name": unit.granth_name,
                    "prakran_name": unit.prakran_name,
                    "chopai_number": unit.chopai_number,
                    "chopai_lines_json": json.dumps(unit.chopai_lines, ensure_ascii=False),
                    "meaning_text": unit.meaning_text,
                    "language_script": unit.language_script,
                    "page_number": unit.page_number,
                    "pdf_path": unit.pdf_path,
                    "source_set": unit.source_set,
                    "normalized_text": unit.normalized_text,
                    "translit_hi_latn": unit.translit_hi_latn,
                    "translit_gu_latn": unit.translit_gu_latn,
                    "chunk_text": unit.chunk_text,
                    "chunk_type": unit.chunk_type,
                }
            )

        return records

    def _recover_pages_with_gemini(
        self,
        pdf_path: Path,
        pages: list[PageText],
        budget: int,
    ) -> tuple[list[PageText], int]:
        if budget <= 0 or not self.gemini.enabled:
            return pages, 0

        candidates = [
            page
            for page in pages
            if (
                page.quality_score < self.settings.ocr_quality_threshold
                or is_garbled_text(page.text)
                or likely_misencoded_indic_text(page.text)
            )
        ]
        if not candidates:
            return pages, 0

        # Prioritize garbled pages first, then lower quality.
        candidates.sort(key=lambda page: (0 if is_garbled_text(page.text) else 1, page.quality_score))
        recoverable = candidates[:budget]

        replacement_text: dict[int, str] = {}
        recovered_count = 0
        for page in recoverable:
            ocr_text = normalize_text(self.gemini.ocr_pdf_page(str(pdf_path), page.page_number))
            if not ocr_text:
                continue

            # Skip weak OCR outputs unless source page is clearly garbled.
            if not is_garbled_text(page.text):
                if is_garbled_text(ocr_text, threshold=0.02) or len(ocr_text) < max(40, int(len(page.text) * 0.5)):
                    continue

            replacement_text[page.page_number] = ocr_text
            recovered_count += 1

        if recovered_count == 0:
            return pages, 0

        upgraded_pages: list[PageText] = []
        for page in pages:
            replacement = replacement_text.get(page.page_number)
            if replacement is None:
                upgraded_pages.append(page)
                continue
            upgraded_pages.append(
                PageText(
                    page_number=page.page_number,
                    text=replacement,
                    extraction_method="gemini_ocr",
                    quality_score=max(page.quality_score, 0.65),
                )
            )

        return upgraded_pages, recovered_count
