from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

from .db import RetrievedUnit

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover - optional in local tests
    genai = None


def _hash_embedding(text: str, dim: int = 256) -> list[float]:
    vector = [0.0] * dim
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(0, min(len(digest), dim), 2):
            idx = digest[i] % dim
            vector[idx] += (digest[i + 1] / 255.0) - 0.5

    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class GeminiClient:
    def __init__(
        self,
        api_key: str | None,
        chat_model: str,
        embedding_model: str,
    ):
        self.api_key = api_key
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.enabled = bool(api_key and genai)
        self._page_ocr_cache: dict[str, str] = {}

        if self.enabled:
            genai.configure(api_key=api_key)

    def embed(self, text: str) -> list[float]:
        text = text.strip()
        if not text:
            return _hash_embedding("empty")

        if not self.enabled:
            return _hash_embedding(text)

        try:
            resp = genai.embed_content(model=self.embedding_model, content=text)
            values = resp["embedding"]
            return [float(v) for v in values]
        except Exception:
            return _hash_embedding(text)

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    def plan_query(
        self,
        question: str,
        conversation_context: list[dict[str, str]] | None = None,
        memory_summary: str = "",
        memory_key_facts: list[str] | None = None,
    ) -> dict:
        if not self.enabled:
            return {
                "intent": "answer_user_question_from_scripture",
                "sub_queries": [],
                "required_facts": [],
            }

        context = "\n".join(
            f"{item.get('role', 'user')}: {item.get('text', '')[:250]}"
            for item in (conversation_context or [])[-4:]
            if item.get("text")
        )
        prompt = (
            "You are a query planner for a scripture-grounded assistant.\n"
            "Return strict JSON only with keys: intent, sub_queries, required_facts.\n"
            "sub_queries should be 2-5 short retrieval-friendly phrases.\n"
            "required_facts should list what must be proven from citations.\n\n"
            f"Session memory summary:\n{memory_summary or 'N/A'}\n\n"
            f"Session key facts:\n{self._format_bullets(memory_key_facts or [])}\n\n"
            f"Recent context:\n{context or 'N/A'}\n\n"
            f"Question:\n{question}\n"
        )

        try:
            model = genai.GenerativeModel(self.chat_model)
            resp = model.generate_content(prompt, generation_config={"temperature": 0.0})
            text = (getattr(resp, "text", "") or "").strip()
            data = self._extract_json_object(text)
            if not data:
                raise ValueError("No JSON object")
            sub_queries = [str(item).strip() for item in data.get("sub_queries", []) if str(item).strip()]
            required_facts = [str(item).strip() for item in data.get("required_facts", []) if str(item).strip()]
            return {
                "intent": str(data.get("intent", "answer_user_question_from_scripture")).strip(),
                "sub_queries": sub_queries[:5],
                "required_facts": required_facts[:8],
            }
        except Exception:
            return {
                "intent": "answer_user_question_from_scripture",
                "sub_queries": [],
                "required_facts": [],
            }

    def generate_answer(
        self,
        question: str,
        citations: list[RetrievedUnit],
        target_style: str,
        conversation_context: list[dict[str, str]] | None = None,
        plan: dict | None = None,
        memory_summary: str = "",
        memory_key_facts: list[str] | None = None,
    ) -> str:
        if not citations:
            return "I could not find this clearly in available texts."

        if not self.enabled:
            return "LLM is not configured. Set GEMINI_API_KEY to enable agentic reasoning."

        prompt = self._build_grounded_prompt(
            question=question,
            citations=citations,
            target_style=target_style,
            conversation_context=conversation_context or [],
            plan=plan or {},
            memory_summary=memory_summary,
            memory_key_facts=memory_key_facts or [],
        )

        try:
            model = genai.GenerativeModel(self.chat_model)
            resp = model.generate_content(prompt)
            text = getattr(resp, "text", "") or ""
            return text.strip() or "I could not find this clearly in available texts."
        except Exception:
            return "I could not find this clearly in available texts."

    def summarize_memory(
        self,
        *,
        existing_summary: str,
        existing_key_facts: list[str],
        latest_user_message: str,
        latest_assistant_message: str,
        conversation_context: list[dict[str, str]] | None = None,
        citations: list[RetrievedUnit] | None = None,
    ) -> tuple[str, list[str]]:
        fallback = self._fallback_memory(
            existing_summary=existing_summary,
            existing_key_facts=existing_key_facts,
            latest_user_message=latest_user_message,
            latest_assistant_message=latest_assistant_message,
            citations=citations or [],
        )

        if not self.enabled:
            return fallback

        history = "\n".join(
            f"{item.get('role', 'user')}: {item.get('text', '')[:240]}"
            for item in (conversation_context or [])[-6:]
            if item.get("text")
        )
        citation_refs = "\n".join(
            f"- {item.granth_name} | {item.prakran_name} | p.{item.page_number}"
            for item in (citations or [])[:5]
        )
        prompt = (
            "You maintain compact memory for an ongoing scripture chat.\n"
            "Return strict JSON only with keys: summary_text, key_facts.\n"
            "summary_text: max 80 words.\n"
            "key_facts: list of <=8 short bullet-style strings.\n"
            "Keep only stable, relevant facts and topic continuity.\n\n"
            f"Existing summary:\n{existing_summary or 'N/A'}\n\n"
            f"Existing key facts:\n{self._format_bullets(existing_key_facts)}\n\n"
            f"Recent context:\n{history or 'N/A'}\n\n"
            f"Latest user message:\n{latest_user_message}\n\n"
            f"Latest assistant message:\n{latest_assistant_message}\n\n"
            f"Latest citation refs:\n{citation_refs or 'N/A'}\n"
        )

        try:
            model = genai.GenerativeModel(self.chat_model)
            resp = model.generate_content(prompt, generation_config={"temperature": 0.0})
            text = (getattr(resp, "text", "") or "").strip()
            data = self._extract_json_object(text)
            if not data:
                return fallback

            summary = str(data.get("summary_text", "")).strip()
            if not summary:
                return fallback

            items = data.get("key_facts", [])
            key_facts = [str(item).strip() for item in items if str(item).strip()]
            if not key_facts:
                key_facts = fallback[1]
            return summary[:900], key_facts[:8]
        except Exception:
            return fallback

    def ocr_pdf_page(self, pdf_path: str, page_number: int) -> str:
        if not self.enabled:
            return ""

        cache_key = f"{pdf_path}:{page_number}"
        if cache_key in self._page_ocr_cache:
            return self._page_ocr_cache[cache_key]

        try:
            import fitz  # type: ignore
        except Exception:
            return ""

        if not Path(pdf_path).exists():
            return ""

        try:
            doc = fitz.open(pdf_path)
            if page_number < 1 or page_number > len(doc):
                return ""

            page = doc[page_number - 1]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_bytes = pix.tobytes("png")

            prompt = (
                "Transcribe this scripture page into clean Unicode text. "
                "Preserve the original language (Hindi/Gujarati) and lines. "
                "Output only plain text, no markdown, no explanation."
            )

            model = genai.GenerativeModel(self.chat_model)
            response = model.generate_content(
                [
                    prompt,
                    {"mime_type": "image/png", "data": image_bytes},
                ],
                generation_config={"temperature": 0.0},
            )
            text = (getattr(response, "text", "") or "").strip()
            self._page_ocr_cache[cache_key] = text
            return text
        except Exception:
            return ""

    def _build_grounded_prompt(
        self,
        question: str,
        citations: list[RetrievedUnit],
        target_style: str,
        conversation_context: list[dict[str, str]],
        plan: dict,
        memory_summary: str,
        memory_key_facts: list[str],
    ) -> str:
        context_parts: list[str] = []
        for idx, citation in enumerate(citations[:6], start=1):
            context_parts.append(
                "\n".join(
                    [
                        f"[{idx}] Granth: {citation.granth_name}",
                        f"[{idx}] Prakran: {citation.prakran_name}",
                        f"[{idx}] Chopai: {' | '.join(citation.chopai_lines)}",
                        f"[{idx}] Meaning: {citation.meaning_text}",
                    ]
                )
            )

        history = "\n".join(
            f"{item.get('role', 'user')}: {item.get('text', '')[:300]}"
            for item in conversation_context[-4:]
            if item.get("text")
        )

        required_facts = "\n".join(f"- {item}" for item in plan.get("required_facts", []) if item)

        return (
            "You are a respectful scripture assistant for Tartam texts.\n"
            "Strict rule: answer using ONLY the provided citations. Do not invent any scripture facts.\n"
            "If evidence is weak or missing, reply exactly: "
            "\"I could not find this clearly in available texts.\" and ask one clarifying question.\n"
            f"Respond in this style/language mode: {target_style}.\n\n"
            "Reasoning task: solve user intent by synthesizing evidence across citations, not by copy-pasting.\n"
            "Output format (must follow):\n"
            "1) Direct Answer: 2-3 lines answering user's intent clearly.\n"
            "2) Explanation from Chopai: 3-6 lines interpreting the meaning in simple language.\n"
            "3) Grounding: one line listing references as [1], [2], etc.\n"
            "Keep the tone devotional and practical, not overly academic.\n\n"
            f"Planned intent: {plan.get('intent', 'answer_user_question_from_scripture')}\n"
            f"Required facts to verify:\n{required_facts or '- derive from strongest citations'}\n\n"
            f"Session memory summary:\n{memory_summary or 'N/A'}\n\n"
            f"Session key facts:\n{self._format_bullets(memory_key_facts)}\n\n"
            f"Recent Chat Context:\n{history or 'N/A'}\n\n"
            f"User Question:\n{question}\n\n"
            f"Citations:\n{'\n\n'.join(context_parts)}\n"
        )

    def _fallback_memory(
        self,
        *,
        existing_summary: str,
        existing_key_facts: list[str],
        latest_user_message: str,
        latest_assistant_message: str,
        citations: list[RetrievedUnit],
    ) -> tuple[str, list[str]]:
        new_summary_parts = [segment for segment in [existing_summary.strip(), latest_user_message.strip()] if segment]
        summary = " | ".join(new_summary_parts)[-900:] if new_summary_parts else latest_user_message.strip()[:900]

        key_facts = [item for item in existing_key_facts if item][:6]
        if latest_user_message.strip():
            key_facts.append(f"User asked: {latest_user_message.strip()[:160]}")
        if citations:
            refs = ", ".join(f"{item.granth_name}/{item.prakran_name}" for item in citations[:3])
            key_facts.append(f"Used sources: {refs}")
        if latest_assistant_message.strip():
            key_facts.append(f"Assistant answered about: {latest_assistant_message.strip()[:160]}")

        deduped: list[str] = []
        seen: set[str] = set()
        for item in key_facts:
            normalized = item.lower().strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(item)
            if len(deduped) >= 8:
                break
        return summary or "Conversation started.", deduped

    def _format_bullets(self, items: list[str]) -> str:
        cleaned = [str(item).strip() for item in items if str(item).strip()]
        if not cleaned:
            return "- N/A"
        return "\n".join(f"- {item}" for item in cleaned[:8])

    def _extract_json_object(self, text: str) -> dict | None:
        text = (text or "").strip()
        if not text:
            return None

        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        snippet = text[start : end + 1]
        try:
            parsed = json.loads(snippet)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
