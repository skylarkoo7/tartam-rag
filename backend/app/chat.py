from __future__ import annotations

import json
import uuid

from .config import Settings
from .db import Database
from .gemini_client import GeminiClient
from .language import detect_style, render_in_style, resolve_output_style
from .models import Citation, ChatRequest, ChatResponse
from .retrieval import RetrievalService


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
            citations = []
            for item in strong_results:
                prev_context, next_context = self.db.get_neighbor_context(
                    current_id=item.unit.id,
                    pdf_path=item.unit.pdf_path,
                    granth_name=item.unit.granth_name,
                    prakran_name=item.unit.prakran_name,
                )
                citations.append(
                    Citation(
                        citation_id=item.unit.id,
                        granth_name=item.unit.granth_name,
                        prakran_name=item.unit.prakran_name,
                        chopai_lines=item.unit.chopai_lines[:2],
                        meaning_text=item.unit.meaning_text,
                        page_number=item.unit.page_number,
                        pdf_path=item.unit.pdf_path,
                        score=item.score,
                        prev_context=prev_context,
                        next_context=next_context,
                    )
                )
            generated = self.gemini.generate_answer(
                question=payload.message,
                citations=[item.unit for item in strong_results],
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
