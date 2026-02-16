from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

from .db import RetrievedUnit
from .text_quality import is_garbled_text

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:  # pragma: no cover - optional in local tests
    genai = None
    genai_types = None


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
        self._page_ocr_cache: dict[str, str] = {}
        self._legacy_decode_cache: dict[str, str] = {}
        self._embedding_dim: int = 768
        self.client: Any | None = None

        if api_key and genai:
            try:
                if genai_types is not None:
                    self.client = genai.Client(
                        api_key=api_key,
                        http_options=genai_types.HttpOptions(timeout=30_000),
                    )
                else:
                    self.client = genai.Client(api_key=api_key)
            except Exception:
                self.client = None

        self.enabled = self.client is not None
        if self.enabled:
            self._bootstrap_embedding_dim()

    def embed(self, text: str) -> list[float]:
        text = text.strip()
        if not text:
            return self._fallback_embedding("empty")

        if not self.enabled or self.client is None:
            return self._fallback_embedding(text)

        try:
            resp = self.client.models.embed_content(model=self.embedding_model, contents=text)
            values = self._extract_embedding_values(resp)
            if not values:
                return self._fallback_embedding(text)
            vector = [float(v) for v in values]
            if len(vector) != self._embedding_dim:
                return self._fallback_embedding(text)
            return vector
        except Exception:
            return self._fallback_embedding(text)

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        items = [text.strip() for text in texts]
        if not items:
            return []

        if not self.enabled or self.client is None:
            return [_hash_embedding(text or "empty", dim=self._embedding_dim) for text in items]

        vectors: list[list[float]] = []
        batch_size = 64
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            try:
                response = self.client.models.embed_content(model=self.embedding_model, contents=batch)
                matrix = self._extract_embedding_matrix(response)
                if len(matrix) != len(batch):
                    raise ValueError("Embedding batch size mismatch")
                for text, vector in zip(batch, matrix):
                    if len(vector) != self._embedding_dim:
                        vectors.append(_hash_embedding(text or "empty", dim=self._embedding_dim))
                    else:
                        vectors.append(vector)
            except Exception:
                vectors.extend([_hash_embedding(text or "empty", dim=self._embedding_dim) for text in batch])

        return vectors

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
            resp = self._generate_content(prompt, temperature=0.0)
            text = self._extract_text(resp).strip()
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
            return "LLM is not configured. Set GEMINI_API_KEY to enable agentic reasoning."

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
            resp = self._generate_content(prompt)
            text = self._extract_text(resp)
            return text.strip() or "I could not find this clearly in available texts."
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
            response = self._generate_content(prompt, temperature=0.1)
            converted = self._extract_text(response).strip()
            return converted or value
        except Exception:
            return value

    def decode_legacy_indic_text(self, text: str) -> str:
        value = (text or "").strip()
        if not value:
            return ""
        if not self.enabled:
            return value

        key = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()
        cached = self._legacy_decode_cache.get(key)
        if cached is not None:
            return cached

        prompt = (
            "The following text is scripture extracted from a legacy-font PDF and appears mojibake/garbled. "
            "Recover it into readable Unicode in the original language (Hindi or Gujarati). "
            "Preserve line breaks and numbering where possible. "
            "Output only corrected text, no explanation.\n\n"
            f"Text:\n{value}"
        )
        try:
            response = self._generate_content(prompt, temperature=0.0)
            recovered = self._extract_text(response).strip()
            if not recovered:
                self._legacy_decode_cache[key] = value
                return value
            if is_garbled_text(recovered, threshold=0.02):
                self._legacy_decode_cache[key] = value
                return value
            self._legacy_decode_cache[key] = recovered
            return recovered
        except Exception:
            self._legacy_decode_cache[key] = value
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
            resp = self._generate_content(prompt, temperature=0.0)
            text = self._extract_text(resp).strip()
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

            image_part: Any = {"mime_type": "image/png", "data": image_bytes}
            if genai_types is not None:
                try:
                    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                except Exception:
                    image_part = {"mime_type": "image/png", "data": image_bytes}

            response = self._generate_content([prompt, image_part], temperature=0.0)
            text = self._extract_text(response).strip()
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
            f"- {key}: {value}"
            for key, value in context_constraints.items()
            if value not in (None, "", [], {})
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

    def _generate_content(self, contents: Any, temperature: float | None = None) -> Any:
        if not self.enabled or self.client is None:
            raise RuntimeError("Gemini client unavailable")

        kwargs: dict[str, Any] = {
            "model": self.chat_model,
            "contents": contents,
        }
        if temperature is not None:
            if genai_types is not None:
                try:
                    kwargs["config"] = genai_types.GenerateContentConfig(temperature=temperature)
                except Exception:
                    kwargs["config"] = {"temperature": temperature}
            else:
                kwargs["config"] = {"temperature": temperature}

        try:
            return self.client.models.generate_content(**kwargs)
        except Exception:
            kwargs.pop("config", None)
            return self.client.models.generate_content(**kwargs)

    def _extract_text(self, response: Any) -> str:
        text = getattr(response, "text", "") or ""
        if text:
            return text

        if isinstance(response, dict):
            if isinstance(response.get("text"), str):
                return response["text"]
            candidates = response.get("candidates") or []
            return self._extract_text_from_candidates(candidates)

        candidates = getattr(response, "candidates", None)
        if candidates:
            return self._extract_text_from_candidates(candidates)

        return ""

    def _extract_text_from_candidates(self, candidates: Any) -> str:
        try:
            for candidate in candidates or []:
                content = getattr(candidate, "content", None) or (
                    candidate.get("content") if isinstance(candidate, dict) else None
                )
                parts = getattr(content, "parts", None) or (content.get("parts") if isinstance(content, dict) else [])
                text_parts: list[str] = []
                for part in parts or []:
                    value = getattr(part, "text", None)
                    if value is None and isinstance(part, dict):
                        value = part.get("text")
                    if isinstance(value, str) and value.strip():
                        text_parts.append(value.strip())
                if text_parts:
                    return "\n".join(text_parts)
        except Exception:
            return ""
        return ""

    def _extract_embedding_values(self, response: Any) -> list[float]:
        embeddings = getattr(response, "embeddings", None)
        if embeddings:
            first = embeddings[0]
            values = getattr(first, "values", None)
            if values is None and isinstance(first, dict):
                values = first.get("values")
            if values:
                return [float(v) for v in values]

        single = getattr(response, "embedding", None)
        if single is not None:
            values = getattr(single, "values", None)
            if values is None and isinstance(single, dict):
                values = single.get("values")
            if values:
                return [float(v) for v in values]

        if isinstance(response, dict):
            if isinstance(response.get("embedding"), dict):
                values = response["embedding"].get("values")
                if values:
                    return [float(v) for v in values]
            if isinstance(response.get("embeddings"), list) and response["embeddings"]:
                first = response["embeddings"][0]
                if isinstance(first, dict):
                    values = first.get("values")
                    if values:
                        return [float(v) for v in values]

        return []

    def _extract_embedding_matrix(self, response: Any) -> list[list[float]]:
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None and isinstance(response, dict):
            embeddings = response.get("embeddings")
        if not embeddings:
            single = self._extract_embedding_values(response)
            return [single] if single else []

        matrix: list[list[float]] = []
        for embedding in embeddings:
            values = getattr(embedding, "values", None)
            if values is None and isinstance(embedding, dict):
                values = embedding.get("values")
            if values:
                matrix.append([float(v) for v in values])
        return matrix

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

    def _fallback_embedding(self, text: str) -> list[float]:
        return _hash_embedding(text or "empty", dim=self._embedding_dim)

    def _bootstrap_embedding_dim(self) -> None:
        if not self.enabled or self.client is None:
            return
        try:
            response = self.client.models.embed_content(model=self.embedding_model, contents="dimension probe")
            values = self._extract_embedding_values(response)
            if values:
                self._embedding_dim = len(values)
        except Exception:
            # Keep deterministic fallback dimension.
            self._embedding_dim = 768

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
