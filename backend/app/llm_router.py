from __future__ import annotations

from typing import Any

from .db import RetrievedUnit
from .gemini_client import GeminiClient
from .openai_client import OpenAIClient


class LLMRouter:
    def __init__(
        self,
        *,
        provider: str,
        gemini: GeminiClient,
        openai: OpenAIClient,
    ):
        self.provider = (provider or "auto").strip().lower()
        if self.provider not in {"auto", "gemini", "openai"}:
            self.provider = "auto"

        self.gemini = gemini
        self.openai = openai
        self.last_generation_error: str | None = None

    @property
    def enabled(self) -> bool:
        if self.provider == "gemini":
            return self.gemini.enabled
        if self.provider == "openai":
            return self.openai.enabled
        return self.gemini.enabled or self.openai.enabled

    @property
    def last_ocr_error(self) -> str | None:
        return self.gemini.last_ocr_error

    def embed(self, text: str) -> list[float]:
        return self.gemini.embed(text)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return self.gemini.embed_many(texts)

    def ocr_pdf_page(self, pdf_path: str, page_number: int) -> str:
        return self.gemini.ocr_pdf_page(pdf_path, page_number)

    def decode_legacy_indic_text(self, text: str) -> str:
        if self.provider == "openai":
            output = self.openai.decode_legacy_indic_text(text)
            self.last_generation_error = self.openai.last_generation_error
            return output

        output = self.gemini.decode_legacy_indic_text(text)
        self.last_generation_error = self.gemini.last_generation_error
        if self.provider == "auto" and self.gemini.last_generation_error and self.openai.enabled:
            fallback = self.openai.decode_legacy_indic_text(text)
            self.last_generation_error = self.openai.last_generation_error
            return fallback
        return output

    def convert_text(self, text: str, target_mode: str) -> str:
        if self.provider == "openai":
            converted = self.openai.convert_text(text, target_mode)
            self.last_generation_error = self.openai.last_generation_error
            return converted

        if self.gemini.enabled:
            converted = self.gemini.convert_text(text, target_mode)
            self.last_generation_error = self.gemini.last_generation_error
            if self.provider == "auto" and self.gemini.last_generation_error and self.openai.enabled:
                fallback = self.openai.convert_text(text, target_mode)
                self.last_generation_error = self.openai.last_generation_error
                return fallback
            return converted

        if self.openai.enabled:
            converted = self.openai.convert_text(text, target_mode)
            self.last_generation_error = self.openai.last_generation_error
            return converted
        return text

    def plan_query(
        self,
        question: str,
        conversation_context: list[dict[str, str]] | None = None,
        memory_summary: str = "",
        memory_key_facts: list[str] | None = None,
    ) -> dict:
        if self.provider == "openai":
            plan = self.openai.plan_query(
                question=question,
                conversation_context=conversation_context,
                memory_summary=memory_summary,
                memory_key_facts=memory_key_facts,
            )
            self.last_generation_error = self.openai.last_generation_error
            return plan

        if self.gemini.enabled:
            plan = self.gemini.plan_query(
                question=question,
                conversation_context=conversation_context,
                memory_summary=memory_summary,
                memory_key_facts=memory_key_facts,
            )
            self.last_generation_error = self.gemini.last_generation_error
            if self.provider == "auto" and self.gemini.last_generation_error and self.openai.enabled:
                fallback = self.openai.plan_query(
                    question=question,
                    conversation_context=conversation_context,
                    memory_summary=memory_summary,
                    memory_key_facts=memory_key_facts,
                )
                self.last_generation_error = self.openai.last_generation_error
                return fallback
            return plan

        if self.openai.enabled:
            plan = self.openai.plan_query(
                question=question,
                conversation_context=conversation_context,
                memory_summary=memory_summary,
                memory_key_facts=memory_key_facts,
            )
            self.last_generation_error = self.openai.last_generation_error
            return plan

        self.last_generation_error = "No LLM provider configured."
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
        if self.provider == "openai":
            answer = self.openai.generate_answer(
                question=question,
                citations=citations,
                target_style=target_style,
                conversation_context=conversation_context,
                plan=plan,
                memory_summary=memory_summary,
                memory_key_facts=memory_key_facts,
                context_constraints=context_constraints,
                grounded_facts=grounded_facts,
            )
            self.last_generation_error = self.openai.last_generation_error
            return answer

        if self.gemini.enabled:
            answer = self.gemini.generate_answer(
                question=question,
                citations=citations,
                target_style=target_style,
                conversation_context=conversation_context,
                plan=plan,
                memory_summary=memory_summary,
                memory_key_facts=memory_key_facts,
                context_constraints=context_constraints,
                grounded_facts=grounded_facts,
            )
            self.last_generation_error = self.gemini.last_generation_error
            if self.provider == "auto" and self.gemini.last_generation_error and self.openai.enabled:
                fallback = self.openai.generate_answer(
                    question=question,
                    citations=citations,
                    target_style=target_style,
                    conversation_context=conversation_context,
                    plan=plan,
                    memory_summary=memory_summary,
                    memory_key_facts=memory_key_facts,
                    context_constraints=context_constraints,
                    grounded_facts=grounded_facts,
                )
                self.last_generation_error = self.openai.last_generation_error
                return fallback
            return answer

        if self.openai.enabled:
            answer = self.openai.generate_answer(
                question=question,
                citations=citations,
                target_style=target_style,
                conversation_context=conversation_context,
                plan=plan,
                memory_summary=memory_summary,
                memory_key_facts=memory_key_facts,
                context_constraints=context_constraints,
                grounded_facts=grounded_facts,
            )
            self.last_generation_error = self.openai.last_generation_error
            return answer

        self.last_generation_error = "No LLM provider configured."
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
        if self.provider == "openai":
            result = self.openai.summarize_memory(
                existing_summary=existing_summary,
                existing_key_facts=existing_key_facts,
                latest_user_message=latest_user_message,
                latest_assistant_message=latest_assistant_message,
                conversation_context=conversation_context,
                citations=citations,
            )
            self.last_generation_error = self.openai.last_generation_error
            return result

        if self.gemini.enabled:
            result = self.gemini.summarize_memory(
                existing_summary=existing_summary,
                existing_key_facts=existing_key_facts,
                latest_user_message=latest_user_message,
                latest_assistant_message=latest_assistant_message,
                conversation_context=conversation_context,
                citations=citations,
            )
            self.last_generation_error = self.gemini.last_generation_error
            if self.provider == "auto" and self.gemini.last_generation_error and self.openai.enabled:
                fallback = self.openai.summarize_memory(
                    existing_summary=existing_summary,
                    existing_key_facts=existing_key_facts,
                    latest_user_message=latest_user_message,
                    latest_assistant_message=latest_assistant_message,
                    conversation_context=conversation_context,
                    citations=citations,
                )
                self.last_generation_error = self.openai.last_generation_error
                return fallback
            return result

        if self.openai.enabled:
            result = self.openai.summarize_memory(
                existing_summary=existing_summary,
                existing_key_facts=existing_key_facts,
                latest_user_message=latest_user_message,
                latest_assistant_message=latest_assistant_message,
                conversation_context=conversation_context,
                citations=citations,
            )
            self.last_generation_error = self.openai.last_generation_error
            return result

        self.last_generation_error = "No LLM provider configured."
        return existing_summary or "Conversation started.", existing_key_facts[:8]

    def as_debug(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "gemini_enabled": self.gemini.enabled,
            "openai_enabled": self.openai.enabled,
            "last_generation_error": self.last_generation_error,
            "last_ocr_error": self.last_ocr_error,
        }
