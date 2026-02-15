from __future__ import annotations

import hashlib
import math
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

    def generate_answer(
        self,
        question: str,
        citations: list[RetrievedUnit],
        target_style: str,
        conversation_context: list[dict[str, str]] | None = None,
    ) -> str:
        if not citations:
            return "I could not find this clearly in available texts."

        if not self.enabled:
            return self._fallback_explanation(question=question, citations=citations)

        prompt = self._build_grounded_prompt(
            question=question,
            citations=citations,
            target_style=target_style,
            conversation_context=conversation_context or [],
        )

        try:
            model = genai.GenerativeModel(self.chat_model)
            resp = model.generate_content(prompt)
            text = getattr(resp, "text", "") or ""
            return text.strip() or self._fallback_explanation(question=question, citations=citations)
        except Exception:
            return self._fallback_explanation(question=question, citations=citations)

    def _build_grounded_prompt(
        self,
        question: str,
        citations: list[RetrievedUnit],
        target_style: str,
        conversation_context: list[dict[str, str]],
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

        return (
            "You are a respectful scripture assistant for Tartam texts.\n"
            "Strict rule: answer using ONLY the provided citations. Do not invent any scripture facts.\n"
            "If evidence is weak or missing, reply exactly: "
            "\"I could not find this clearly in available texts.\" and ask one clarifying question.\n"
            f"Respond in this style/language mode: {target_style}.\n\n"
            "Output format (must follow):\n"
            "1) Direct Answer: 2-3 lines answering user's intent clearly.\n"
            "2) Explanation from Chopai: 3-6 lines interpreting the meaning in simple language.\n"
            "3) Grounding: one line listing references as [1], [2], etc.\n"
            "Keep the tone devotional and practical, not overly academic.\n\n"
            f"Recent Chat Context:\n{history or 'N/A'}\n\n"
            f"User Question:\n{question}\n\n"
            f"Citations:\n{'\n\n'.join(context_parts)}\n"
        )

    def _fallback_explanation(self, question: str, citations: list[RetrievedUnit]) -> str:
        top = citations[:2]
        if not top:
            return "I could not find this clearly in available texts."

        meanings = " ".join(item.meaning_text for item in top if item.meaning_text).strip()
        if not meanings:
            meanings = " ".join(item.chunk_text for item in top).strip()

        references = ", ".join(f"{item.granth_name}/{item.prakran_name}" for item in top)

        return (
            f"Direct Answer: Based on the matched chopai context, your query \"{question}\" relates to this teaching.\n"
            f"Explanation from Chopai: {meanings[:700]}\n"
            f"Grounding: {references}"
        )
