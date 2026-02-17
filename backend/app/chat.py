from __future__ import annotations

import json
import uuid
from dataclasses import replace

from .config import Settings
from .db import Database, RetrievedUnit
from .language import detect_style, normalize_text, render_in_style, resolve_output_style, transliterate_to_latin
from .llm_router import LLMRouter
from .models import Citation, ChatRequest, ChatResponse
from .query_context import (
    QueryContext,
    build_query_hints,
    next_session_context,
    parse_query_context,
    parse_session_context,
    unit_matches_query,
    unit_matches_prakran,
)
from .retrieval import RetrievalService
from .text_quality import is_garbled_text, safe_display_text


class ChatService:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        retrieval: RetrievalService,
        llm: LLMRouter,
    ):
        self.settings = settings
        self.db = db
        self.retrieval = retrieval
        self.llm = llm

    def respond(self, payload: ChatRequest) -> ChatResponse:
        detected = detect_style(payload.message)
        answer_style = resolve_output_style(payload.style_mode, detected)
        recent_messages = self.db.get_recent_messages(payload.session_id, limit=8)
        memory = self.db.get_session_memory(payload.session_id) or {}
        memory_summary = str(memory.get("summary_text", "")).strip()
        memory_key_facts = [str(item) for item in memory.get("key_facts", []) if str(item).strip()]

        filters = payload.filters or None
        granth_filter = (filters.granth or "").strip() if filters else ""
        prakran_filter = (filters.prakran or "").strip() if filters else ""

        granths, _ = self.db.list_filters()
        prior_context = parse_session_context(self.db.get_session_context(payload.session_id))
        query_context = parse_query_context(
            payload.message,
            granths=granths,
            prior=prior_context,
            filter_granth=granth_filter or None,
            filter_prakran=prakran_filter or None,
        )

        retrieval_granth = query_context.granth_name
        retrieval_prakran = prakran_filter if prakran_filter and not query_context.has_prakran_constraint else None
        if retrieval_prakran and retrieval_prakran.lower() == "unknown prakran":
            retrieval_prakran = None

        top_k = payload.top_k or self.settings.retrieval_top_k
        evidence_units: list[RetrievedUnit] = []
        count_result: int | None = None
        if query_context.requires_count:
            count_result = self.db.count_chopai_reference(
                granth_name=query_context.granth_name,
                prakran_number=query_context.prakran_number,
                prakran_range=(
                    (query_context.prakran_range_start, query_context.prakran_range_end)
                    if query_context.prakran_range_start is not None and query_context.prakran_range_end is not None
                    else None
                ),
            )

        grounded_facts = self._build_grounded_facts(query_context, count_result)

        if not self.llm.enabled:
            answer = (
                "LLM is not configured. This app is set to agentic mode and requires a valid "
                "GEMINI_API_KEY or OPENAI_API_KEY to reason over retrieved chunks."
            )
            follow_up = "Add GEMINI_API_KEY or OPENAI_API_KEY in backend/.env and restart backend."
            citations = []
            not_found = True
            scores = []
            plan = {
                "intent": "llm_required",
                "sub_queries": [],
                "required_facts": [],
                "query_context": self._context_payload(query_context),
            }
        else:
            plan = self.llm.plan_query(
                question=payload.message,
                conversation_context=recent_messages,
                memory_summary=memory_summary,
                memory_key_facts=memory_key_facts,
            )
            query_list = self._build_agentic_query_list(payload.message, plan, query_context)
            aggregated = self._agentic_retrieve(
                queries=query_list,
                style=detected,
                top_k=top_k,
                granth=retrieval_granth,
                prakran=retrieval_prakran,
            )
            merged = self._merge_reference_hits(aggregated, query_context, top_k=top_k)
            constrained = self._apply_query_constraints(merged, query_context)

            scores = [score for _, score in constrained]
            strong_results = [pair for pair in constrained if pair[1] >= self.settings.minimum_grounding_score]
            strong_results = self._diversify_reference_results(
                strong_results,
                query_context=query_context,
                max_items=max(top_k, 4),
            )

            if self._is_ambiguous_reference(query_context, strong_results):
                strong_results = []

            if not strong_results:
                answer = "I could not find this clearly in available texts."
                follow_up = self._follow_up_for_not_found(query_context)
                citations = []
                not_found = True
            else:
                recovered_pairs = [(self._recover_unit_if_needed(unit), score) for unit, score in strong_results]
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
                            chopai_number=unit.chopai_number,
                            prakran_chopai_index=unit.prakran_chopai_index,
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
                        "I found related pages, but their text still appears unreadable from current extraction. "
                        "Please re-index with OCR recovery enabled or use OCR-processed PDFs for reliable answers."
                    )
                    ocr_hint = self._compact_error(self.llm.last_ocr_error)
                    if ocr_hint:
                        answer = f"{answer}\n\nOCR status: {ocr_hint}"
                    follow_up = "You can also ask with exact granth + prakran + page for targeted OCR recovery."
                    not_found = True
                else:
                    evidence_units = [unit for unit, _ in explainable_pairs][: max(top_k, 4)]
                    generated = self.llm.generate_answer(
                        question=payload.message,
                        citations=evidence_units,
                        target_style=answer_style,
                        conversation_context=recent_messages,
                        plan=plan,
                        memory_summary=memory_summary,
                        memory_key_facts=memory_key_facts,
                        context_constraints=self._context_payload(query_context),
                        grounded_facts=grounded_facts,
                    )
                    if (
                        generated.strip().lower().startswith("i could not find this clearly in available texts")
                        and self.llm.last_generation_error
                    ):
                        answer = render_in_style(
                            "I could not generate a grounded explanation right now because the LLM call failed. "
                            "Please retry after checking Gemini API connectivity/model access.",
                            answer_style,
                        )
                        follow_up = "Retry now or confirm GEMINI_API_KEY/model access from backend."
                        not_found = True
                    else:
                        if query_context.requires_count and count_result is not None and count_result > 0:
                            count_line = (
                                f"Direct Answer: For the requested scope, I found {count_result} distinct chopai numbers in the indexed text.\n"
                            )
                            if str(count_result) not in generated:
                                generated = f"{count_line}\n{generated}"
                        answer = render_in_style(generated, answer_style)
                        if answer.strip().lower().startswith("i could not find this clearly in available texts"):
                            follow_up = self._follow_up_for_not_found(query_context)
                            not_found = True
                        else:
                            follow_up = None
                            not_found = False

        updated_context = next_session_context(prior_context, query_context)
        self._persist_session_context(payload.session_id, updated_context)
        self._persist_exchange(
            session_id=payload.session_id,
            user_text=payload.message,
            user_style=detected,
            assistant_text=answer,
            assistant_style=answer_style,
            citations=citations,
        )
        self._update_session_memory(
            session_id=payload.session_id,
            existing_summary=memory_summary,
            existing_key_facts=memory_key_facts,
            latest_user_message=payload.message,
            latest_assistant_message=answer,
            recent_messages=recent_messages,
            evidence_units=evidence_units,
        )

        debug = (
            {
                "retrieval_scores": scores,
                "plan": plan,
                "query_context": self._context_payload(query_context),
                "grounded_facts": grounded_facts,
                "llm_enabled": self.llm.enabled,
                "llm_generation_error": self.llm.last_generation_error,
                "ocr_error": self.llm.last_ocr_error,
                "llm_provider": self.llm.provider,
            }
            if self.settings.allow_debug_payloads
            else None
        )
        return ChatResponse(
            answer=answer,
            answer_style=answer_style,
            not_found=not_found,
            follow_up_question=follow_up,
            citations=citations,
            context_state=self._context_payload_from_state(updated_context),
            debug=debug,
        )

    def _build_agentic_query_list(self, question: str, plan: dict, query_context: QueryContext) -> list[str]:
        queries = [question.strip()]
        for item in plan.get("sub_queries", []):
            text = str(item).strip()
            if text and text.lower() not in {q.lower() for q in queries}:
                queries.append(text)
        for hint in build_query_hints(query_context):
            if hint and hint.lower() not in {q.lower() for q in queries}:
                queries.append(hint)
        return queries[:10]

    def _agentic_retrieve(
        self,
        queries: list[str],
        style: str,
        top_k: int,
        granth: str | None,
        prakran: str | None,
    ) -> list[tuple[RetrievedUnit, float]]:
        score_by_id: dict[str, float] = {}
        unit_by_id: dict[str, RetrievedUnit] = {}

        per_query_limit = max(top_k * 2, 8)
        for query_idx, query in enumerate(queries):
            results = self.retrieval.search(
                query=query,
                style=style,
                top_k=per_query_limit,
                granth=granth,
                prakran=prakran,
            )
            query_weight = 1.0 / (1.0 + (query_idx * 0.35))
            for rank, item in enumerate(results, start=1):
                rank_bonus = 1.0 / (40 + rank)
                blended = (item.score * query_weight) + rank_bonus
                score_by_id[item.unit.id] = score_by_id.get(item.unit.id, 0.0) + blended
                unit_by_id[item.unit.id] = item.unit

        ranked_ids = sorted(score_by_id.keys(), key=lambda item_id: score_by_id[item_id], reverse=True)
        return [(unit_by_id[item_id], score_by_id[item_id]) for item_id in ranked_ids[: max(top_k, 4)]]

    def _merge_reference_hits(
        self,
        ranked: list[tuple[RetrievedUnit, float]],
        query_context: QueryContext,
        *,
        top_k: int,
    ) -> list[tuple[RetrievedUnit, float]]:
        if not query_context.has_reference_constraint:
            return ranked

        score_by_id: dict[str, float] = {unit.id: score for unit, score in ranked}
        unit_by_id: dict[str, RetrievedUnit] = {unit.id: unit for unit, _ in ranked}

        reference_hits = self.db.lookup_reference_units(
            granth_name=query_context.granth_name,
            chopai_number=query_context.chopai_number,
            prakran_number=query_context.prakran_number,
            prakran_range=(
                (query_context.prakran_range_start, query_context.prakran_range_end)
                if query_context.prakran_range_start is not None and query_context.prakran_range_end is not None
                else None
            ),
            limit=max(top_k * 5, 20),
        )

        for rank, unit in enumerate(reference_hits, start=1):
            score = 0.25 + (1.0 / (30 + rank))
            score_by_id[unit.id] = max(score_by_id.get(unit.id, 0.0), score)
            unit_by_id[unit.id] = unit

        ranked_ids = sorted(score_by_id.keys(), key=lambda item_id: score_by_id[item_id], reverse=True)
        return [(unit_by_id[item_id], score_by_id[item_id]) for item_id in ranked_ids[: max(top_k * 2, 10)]]

    def _apply_query_constraints(
        self,
        ranked: list[tuple[RetrievedUnit, float]],
        query_context: QueryContext,
    ) -> list[tuple[RetrievedUnit, float]]:
        if not query_context.has_reference_constraint:
            return ranked

        constrained = [(unit, score) for unit, score in ranked if unit_matches_query(unit, query_context)]
        if constrained:
            return constrained
        return []

    def _follow_up_for_not_found(self, query_context: QueryContext) -> str:
        if query_context.granth_name is None and (
            query_context.prakran_number is not None
            or query_context.chopai_number is not None
            or query_context.prakran_range_start is not None
        ):
            return "Please specify granth name as well, because this reference appears in multiple granths."
        if query_context.chopai_number is not None and query_context.prakran_number is not None:
            return (
                "I could not match that exact granth/prakran/chopai combination in indexed text. "
                "Please share granth name and a key phrase from the chopai."
            )
        if query_context.has_prakran_constraint:
            return (
                "I could not match that prakran reference confidently. "
                "Please add granth name or ask with a direct chopai phrase."
            )
        return "Please mention granth, prakran, or a key chopai phrase so I can search better."

    def _build_grounded_facts(self, query_context: QueryContext, count_result: int | None) -> list[str]:
        facts: list[str] = []
        if query_context.granth_name:
            facts.append(f"Focused granth: {query_context.granth_name}")
        if query_context.prakran_number is not None:
            facts.append(f"Requested prakran: {query_context.prakran_number}")
        if query_context.prakran_range_start is not None and query_context.prakran_range_end is not None:
            facts.append(f"Requested prakran range: {query_context.prakran_range_start} to {query_context.prakran_range_end}")
        if query_context.chopai_number is not None:
            facts.append(f"Requested chopai: {query_context.chopai_number}")
        if query_context.requires_count and count_result is not None and count_result > 0:
            facts.append(f"Indexed count result: {count_result} distinct chopai numbers in requested scope.")
        elif query_context.requires_count:
            facts.append("Count result: no distinct chopai numbers found for requested scope.")
        return facts

    def _diversify_reference_results(
        self,
        ranked_pairs: list[tuple[RetrievedUnit, float]],
        *,
        query_context: QueryContext,
        max_items: int,
    ) -> list[tuple[RetrievedUnit, float]]:
        if not ranked_pairs:
            return []

        sorted_pairs = sorted(ranked_pairs, key=lambda item: item[1], reverse=True)
        if query_context.prakran_range_start is None or query_context.prakran_range_end is None:
            return sorted_pairs[:max_items]

        requested_prakrans = query_context.prakran_numbers(max_span=24)
        if not requested_prakrans:
            return sorted_pairs[:max_items]

        per_prakran: dict[int, int] = {number: 0 for number in requested_prakrans}
        diversified: list[tuple[RetrievedUnit, float]] = []
        overflow: list[tuple[RetrievedUnit, float]] = []

        for unit, score in sorted_pairs:
            matched = next((number for number in requested_prakrans if unit_matches_prakran(unit, number)), None)
            if matched is None:
                overflow.append((unit, score))
                continue
            if per_prakran[matched] < 2:
                diversified.append((unit, score))
                per_prakran[matched] += 1
            else:
                overflow.append((unit, score))

            if len(diversified) >= max_items:
                return diversified[:max_items]

        for pair in overflow:
            diversified.append(pair)
            if len(diversified) >= max_items:
                break

        return diversified[:max_items]

    def _compact_error(self, value: str | None) -> str | None:
        if not value:
            return None
        text = value.strip()
        if not text:
            return None
        lowered = text.lower()
        if "nodename nor servname provided" in lowered or "temporary failure in name resolution" in lowered:
            return "Network/DNS issue while contacting Gemini."
        if "permission" in lowered or "unauthorized" in lowered or "api key" in lowered:
            return "Gemini authentication/permissions issue."
        return text[:180]

    def _is_ambiguous_reference(
        self,
        query_context: QueryContext,
        strong_results: list[tuple[RetrievedUnit, float]],
    ) -> bool:
        if query_context.granth_name is not None:
            return False
        if not (query_context.chopai_number is not None or query_context.prakran_number is not None):
            return False
        if not strong_results:
            return False
        granths = {unit.granth_name for unit, _ in strong_results}
        return len(granths) > 1

    def _context_payload(self, query_context: QueryContext) -> dict:
        return {
            "intent": query_context.intent,
            "granth_name": query_context.granth_name,
            "prakran_number": query_context.prakran_number,
            "prakran_range_start": query_context.prakran_range_start,
            "prakran_range_end": query_context.prakran_range_end,
            "chopai_number": query_context.chopai_number,
            "requires_summary": query_context.requires_summary,
            "requires_count": query_context.requires_count,
            "context_carried": query_context.context_carried,
            "notes": query_context.notes,
        }

    def _context_payload_from_state(self, context_state: object) -> dict:
        return {
            "granth_name": getattr(context_state, "granth_name", None),
            "prakran_number": getattr(context_state, "prakran_number", None),
            "prakran_range_start": getattr(context_state, "prakran_range_start", None),
            "prakran_range_end": getattr(context_state, "prakran_range_end", None),
            "chopai_number": getattr(context_state, "chopai_number", None),
        }

    def _persist_session_context(self, session_id: str, context_state: object) -> None:
        self.db.upsert_session_context(
            session_id=session_id,
            granth_name=getattr(context_state, "granth_name", None),
            prakran_number=getattr(context_state, "prakran_number", None),
            prakran_range_start=getattr(context_state, "prakran_range_start", None),
            prakran_range_end=getattr(context_state, "prakran_range_end", None),
            chopai_number=getattr(context_state, "chopai_number", None),
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

        ocr_text = self.llm.ocr_pdf_page(unit.pdf_path, unit.page_number)
        ocr_text = normalize_text(ocr_text)
        if ocr_text and not is_garbled_text(ocr_text, threshold=0.12):
            return self._unit_from_recovered_text(unit, ocr_text, suffix="ocr")

        decode_source = "\n".join(
            [
                " ".join(unit.chopai_lines[:2]),
                unit.meaning_text[:420],
            ]
        ).strip()
        if not decode_source:
            return unit
        repaired = normalize_text(self.llm.decode_legacy_indic_text(decode_source))
        if not repaired or is_garbled_text(repaired, threshold=0.05):
            return unit
        return self._unit_from_recovered_text(unit, repaired, suffix="decoded")

    def _unit_from_recovered_text(self, unit: RetrievedUnit, text: str, suffix: str) -> RetrievedUnit:
        lines = [normalize_text(item) for item in text.splitlines() if normalize_text(item)]
        if not lines:
            lines = [normalize_text(text)]
        lines = [line for line in lines if line]
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
            chunk_type=f"{unit.chunk_type}_{suffix}",
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

    def _update_session_memory(
        self,
        session_id: str,
        existing_summary: str,
        existing_key_facts: list[str],
        latest_user_message: str,
        latest_assistant_message: str,
        recent_messages: list[dict[str, str]],
        evidence_units: list[RetrievedUnit],
    ) -> None:
        context = [
            *recent_messages[-6:],
            {"role": "user", "text": latest_user_message},
            {"role": "assistant", "text": latest_assistant_message},
        ]
        summary, key_facts = self.llm.summarize_memory(
            existing_summary=existing_summary,
            existing_key_facts=existing_key_facts,
            latest_user_message=latest_user_message,
            latest_assistant_message=latest_assistant_message,
            conversation_context=context,
            citations=evidence_units,
        )
        self.db.upsert_session_memory(session_id=session_id, summary_text=summary, key_facts=key_facts)
