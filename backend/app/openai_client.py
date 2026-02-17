from __future__ import annotations

import json
from typing import Any

from .db import RetrievedUnit
from .text_quality import is_garbled_text

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore[misc]


class OpenAIClient:
    def __init__(self, api_key: str | None, chat_model: str):
        self.api_key = api_key
        self.chat_model = chat_model
        self.client: Any | None = None
        self.last_generation_error: str | None = None

        if api_key and OpenAI:
            try:
                self.client = OpenAI(api_key=api_key)
            except Exception:
                self.client = None

        self.enabled = self.client is not None

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
            text = self._complete(prompt, temperature=0.0).strip()
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
        context_constraints: dict | None = None,
        grounded_facts: list[str] | None = None,
    ) -> str:
        if not citations:
            return "I could not find this clearly in available texts."
        if not self.enabled:
            return "I could not find this clearly in available texts."

        prompt = self._build_grounded_prompt(
            question=question,
            citations=citations,
            target_style=target_style,
            conversation_context=conversation_context or [],
            plan=plan or {},
            memory_summary=memory_summary,
            memory_key_facts=memory_key_facts or [],
            context_constraints=context_constraints or {},
            grounded_facts=grounded_facts or [],
        )
        try:
            text = self._complete(prompt, temperature=0.2).strip()
            return text or "I could not find this clearly in available texts."
        except Exception:
            return "I could not find this clearly in available texts."

    def convert_text(self, text: str, target_mode: str) -> str:
        value = (text or "").strip()
        if not value:
            return ""
        if not self.enabled:
            return value

        prompt = (
            "Convert the following text according to requested mode.\n"
            "Return only converted text. No bullets, no explanation.\n"
            "Modes:\n"
            "- en: Translate to natural English.\n"
            "- hi: Translate to natural Hindi in Devanagari script.\n"
            "- gu: Translate to natural Gujarati in Gujarati script.\n"
            "- hi_latn: Hindi language in Latin script.\n"
            "- gu_latn: Gujarati language in Latin script.\n"
            "- en_deva: Keep English words, write phonetically in Devanagari script only.\n"
            "- en_gu: Keep English words, write phonetically in Gujarati script only.\n"
            f"Target mode: {target_mode}\n\n"
            f"Text:\n{value}"
        )
        try:
            converted = self._complete(prompt, temperature=0.1).strip()
            return converted or value
        except Exception:
            return value

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
            text = self._complete(prompt, temperature=0.0).strip()
            data = self._extract_json_object(text)
            if not data:
                return fallback
            summary = str(data.get("summary_text", "")).strip()
            items = data.get("key_facts", [])
            key_facts = [str(item).strip() for item in items if str(item).strip()]
            if not summary:
                summary = fallback[0]
            if not key_facts:
                key_facts = fallback[1]
            return summary[:900], key_facts[:8]
        except Exception:
            return fallback

    def decode_legacy_indic_text(self, text: str) -> str:
        value = (text or "").strip()
        if not value:
            return ""
        if not self.enabled:
            return value
        prompt = (
            "The following text is mojibake from legacy Hindi/Gujarati font extraction. "
            "Convert it into readable Unicode (Devanagari or Gujarati). "
            "Do not repeat garbled Latin symbols. "
            "Preserve numbering and line breaks. Output only corrected text.\n\n"
            f"Text:\n{value}"
        )
        try:
            recovered = self._complete(prompt, temperature=0.0).strip()
            if not recovered or recovered == value or is_garbled_text(recovered, threshold=0.03):
                return value
            return recovered
        except Exception:
            return value

    def _complete(self, prompt: str, temperature: float | None = None) -> str:
        if not self.enabled or self.client is None:
            raise RuntimeError("OpenAI client unavailable")

        try:
            response = self.client.responses.create(
                model=self.chat_model,
                input=prompt,
                temperature=temperature if temperature is not None else 0.2,
            )
            text = (getattr(response, "output_text", None) or "").strip()
            if text:
                self.last_generation_error = None
                return text
        except Exception:
            pass

        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                temperature=temperature if temperature is not None else 0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            text = (
                response.choices[0].message.content
                if response and response.choices and response.choices[0].message
                else ""
            )
            text = (text or "").strip()
            if text:
                self.last_generation_error = None
                return text
            raise ValueError("No text in OpenAI response")
        except Exception as exc:
            self.last_generation_error = f"{type(exc).__name__}: {exc}"
            raise

    def _build_grounded_prompt(
        self,
        question: str,
        citations: list[RetrievedUnit],
        target_style: str,
        conversation_context: list[dict[str, str]],
        plan: dict,
        memory_summary: str,
        memory_key_facts: list[str],
        context_constraints: dict[str, Any],
        grounded_facts: list[str],
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
        constraints = "\n".join(
            f"- {key}: {value}" for key, value in context_constraints.items() if value not in (None, "", [], {})
        )
        deterministic_facts = "\n".join(f"- {item}" for item in grounded_facts if item)

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
            f"User reference constraints:\n{constraints or '- none'}\n\n"
            f"Deterministic facts:\n{deterministic_facts or '- none'}\n\n"
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
