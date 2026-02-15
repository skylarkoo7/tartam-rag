from __future__ import annotations

import json
import uuid
from dataclasses import replace

from .config import Settings
from .db import Database, RetrievedUnit
from .gemini_client import GeminiClient
from .language import detect_style, normalize_text, render_in_style, resolve_output_style, transliterate_to_latin
from .models import Citation, ChatRequest, ChatResponse
from .retrieval import RetrievalService
from .text_quality import is_garbled_text, safe_display_text


class ChatService:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        retrieval: RetrievalService,
        gemini: GeminiClient,
    ):
        self.settings = settings
        self.db = db
        self.retrieval = retrieval
        self.gemini = gemini

    def respond(self, payload: ChatRequest) -> ChatResponse:
        detected = detect_style(payload.message)
        answer_style = resolve_output_style(payload.style_mode, detected)

        filters = payload.filters or None
        granth = filters.granth if filters else None
        prakran = filters.prakran if filters else None

        top_k = payload.top_k or self.settings.retrieval_top_k

        retrieval_results = self.retrieval.search(
            query=payload.message,
            style=detected,
            top_k=top_k,
            granth=granth,
            prakran=prakran,
        )

        scores = [item.score for item in retrieval_results]
        strong_results = [item for item in retrieval_results if item.score >= self.settings.minimum_grounding_score]

        if not strong_results:
            answer = "I could not find this clearly in available texts."
            follow_up = "Please mention granth, prakran, or a key chopai phrase so I can search better."
            citations: list[Citation] = []
            not_found = True
        else:
            recovered_pairs = [(self._recover_unit_if_needed(item.unit), item.score) for item in strong_results]
            explainable_pairs = [pair for pair in recovered_pairs if not is_garbled_text(pair[0].chunk_text)]

            citations = []
            for unit, score in recovered_pairs:
                prev_context, next_context = self.db.get_neighbor_context(
                    current_id=unit.id,
                    pdf_path=unit.pdf_path,
                    granth_name=unit.granth_name,
                    prakran_name=unit.prakran_name,
                )
                citations.append(
                    Citation(
                        citation_id=unit.id,
                        granth_name=unit.granth_name,
                        prakran_name=unit.prakran_name,
                        chopai_lines=self._safe_chopai_lines(unit.chopai_lines),
                        meaning_text=safe_display_text(
                            unit.meaning_text,
                            fallback="Meaning text could not be decoded from this PDF page.",
                        ),
                        page_number=unit.page_number,
                        pdf_path=unit.pdf_path,
                        score=score,
                        prev_context=safe_display_text(prev_context or "", fallback="") or None,
                        next_context=safe_display_text(next_context or "", fallback="") or None,
                    )
                )

            if not explainable_pairs:
                answer = (
                    "I found related pages, but their text appears encoded incorrectly in the current PDF extraction. "
                    "Please enable Gemini OCR recovery with API key or use OCR-processed PDFs for readable output."
                )
                follow_up = "You can also ask with exact granth and page number for targeted OCR recovery."
                not_found = True
            else:
                generated = self.gemini.generate_answer(
                    question=payload.message,
                    citations=[unit for unit, _ in explainable_pairs],
                    target_style=answer_style,
                    conversation_context=self.db.get_recent_messages(payload.session_id, limit=6),
                )
                answer = render_in_style(generated, answer_style)
                follow_up = None
                not_found = False

        self._persist_exchange(
            session_id=payload.session_id,
            user_text=payload.message,
            user_style=detected,
            assistant_text=answer,
            assistant_style=answer_style,
            citations=citations,
        )

        debug = {"retrieval_scores": scores} if self.settings.allow_debug_payloads else None
        return ChatResponse(
            answer=answer,
            answer_style=answer_style,
            not_found=not_found,
            follow_up_question=follow_up,
            citations=citations,
            debug=debug,
        )

    def _safe_chopai_lines(self, lines: list[str]) -> list[str]:
        cleaned = [
            safe_display_text(line, fallback="")
            for line in lines[:2]
            if safe_display_text(line, fallback="")
        ]
        if cleaned:
            return cleaned
        return ["Chopai text could not be decoded from this PDF page."]

    def _recover_unit_if_needed(self, unit: RetrievedUnit) -> RetrievedUnit:
        if not is_garbled_text(unit.chunk_text):
            return unit

        if not self.settings.allow_gemini_page_ocr_recovery:
            return unit

        ocr_text = self.gemini.ocr_pdf_page(unit.pdf_path, unit.page_number)
        ocr_text = normalize_text(ocr_text)
        if not ocr_text or is_garbled_text(ocr_text, threshold=0.12):
            return unit

        lines = [normalize_text(item) for item in ocr_text.splitlines() if normalize_text(item)]
        if not lines:
            return unit

        chopai_lines = lines[:2]
        meaning_text = " ".join(lines[2:]) if len(lines) > 2 else " ".join(lines)
        combined = "\n".join(lines[:60])
        translit = transliterate_to_latin(combined).lower()

        return replace(
            unit,
            chopai_lines=chopai_lines,
            meaning_text=meaning_text,
            chunk_text=combined,
            normalized_text=normalize_text(combined),
            translit_hi_latn=translit,
            translit_gu_latn=translit,
            chunk_type=f"{unit.chunk_type}_ocr",
        )

    def _persist_exchange(
        self,
        session_id: str,
        user_text: str,
        user_style: str,
        assistant_text: str,
        assistant_style: str,
        citations: list[Citation],
    ) -> None:
        self.db.add_message(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            text=user_text,
            style_tag=user_style,
            citations_json=None,
        )
        self.db.add_message(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            text=assistant_text,
            style_tag=assistant_style,
            citations_json=json.dumps([citation.model_dump() for citation in citations], ensure_ascii=False),
        )
