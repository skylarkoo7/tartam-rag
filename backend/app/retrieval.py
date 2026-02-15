from __future__ import annotations

from dataclasses import dataclass

from .db import Database, RetrievedUnit
from .gemini_client import GeminiClient
from .language import query_variants
from .vector_store import VectorStore


@dataclass(slots=True)
class RetrievalResult:
    unit: RetrievedUnit
    score: float


class RetrievalService:
    def __init__(self, db: Database, vectors: VectorStore, gemini: GeminiClient):
        self.db = db
        self.vectors = vectors
        self.gemini = gemini

    def search(
        self,
        query: str,
        style: str,
        top_k: int,
        granth: str | None,
        prakran: str | None,
    ) -> list[RetrievalResult]:
        variants = query_variants(query, style)
        if not variants:
            return []

        lexical_ranked: list[tuple[RetrievedUnit, float]] = []
        for variant in variants:
            lexical_ranked.extend(self.db.search_fts(variant, limit=max(top_k * 3, 12), granth=granth, prakran=prakran))

        vector_ranked: list[tuple[RetrievedUnit, float]] = []
        if self.vectors.available:
            where: dict | None = None
            where_terms: dict = {}
            if granth:
                where_terms["granth_name"] = granth
            if prakran:
                where_terms["prakran_name"] = prakran
            if where_terms:
                where = where_terms

            for variant in variants:
                emb = self.gemini.embed(variant)
                vector_hits = self.vectors.query(query_embedding=emb, limit=max(top_k * 3, 12), where=where)
                ids = [item_id for item_id, _ in vector_hits]
                by_id = self.db.fetch_units_by_ids(ids)
                for item_id, score in vector_hits:
                    unit = by_id.get(item_id)
                    if unit is not None:
                        vector_ranked.append((unit, score))

        fused = reciprocal_rank_fusion(lexical_ranked, vector_ranked, k=50)
        return fused[:top_k]


def reciprocal_rank_fusion(
    lexical: list[tuple[RetrievedUnit, float]],
    vector: list[tuple[RetrievedUnit, float]],
    k: int = 50,
) -> list[RetrievalResult]:
    acc: dict[str, float] = {}
    units: dict[str, RetrievedUnit] = {}

    # Deduplicate each stream by first-seen order.
    lex_stream: list[RetrievedUnit] = []
    seen: set[str] = set()
    for unit, _ in sorted(lexical, key=lambda item: item[1], reverse=True):
        if unit.id in seen:
            continue
        seen.add(unit.id)
        lex_stream.append(unit)

    vec_stream: list[RetrievedUnit] = []
    seen = set()
    for unit, _ in sorted(vector, key=lambda item: item[1], reverse=True):
        if unit.id in seen:
            continue
        seen.add(unit.id)
        vec_stream.append(unit)

    for rank, unit in enumerate(lex_stream, start=1):
        acc[unit.id] = acc.get(unit.id, 0.0) + (1.0 / (k + rank))
        units[unit.id] = unit
    for rank, unit in enumerate(vec_stream, start=1):
        acc[unit.id] = acc.get(unit.id, 0.0) + (1.0 / (k + rank))
        units[unit.id] = unit

    ranked_ids = sorted(acc.keys(), key=lambda item_id: acc[item_id], reverse=True)
    return [RetrievalResult(unit=units[item_id], score=acc[item_id]) for item_id in ranked_ids]
