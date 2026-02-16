from __future__ import annotations

from pathlib import Path

try:
    import chromadb
except Exception:  # pragma: no cover
    chromadb = None


class VectorStore:
    def __init__(self, persist_path: Path, collection_name: str = "tartam_chunks"):
        self.available = False
        self.collection = None
        self.client = None
        self.collection_name = collection_name

        if chromadb is None:
            return

        self.client = chromadb.PersistentClient(path=str(persist_path))
        self.collection = self.client.get_or_create_collection(collection_name)
        self.available = True

    def clear(self) -> None:
        if not self.available:
            return
        if self.client is None:
            return

        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(self.collection_name)

    def upsert(self, ids: list[str], texts: list[str], embeddings: list[list[float]], metadatas: list[dict]) -> None:
        if not self.available or not ids:
            return

        batch_size = self._safe_batch_size(default=5000)
        for start in range(0, len(ids), batch_size):
            end = min(start + batch_size, len(ids))
            self.collection.upsert(
                ids=ids[start:end],
                documents=texts[start:end],
                embeddings=embeddings[start:end],
                metadatas=metadatas[start:end],
            )

    def query(
        self,
        query_embedding: list[float],
        limit: int,
        where: dict | None = None,
    ) -> list[tuple[str, float]]:
        if not self.available:
            return []
        try:
            result = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where,
                include=["distances"],
            )
        except Exception:
            # If embedding dimensions drift across model upgrades, lexical retrieval still works.
            return []

        ids_list = result.get("ids", [[]])[0]
        dists = result.get("distances", [[]])[0]

        output: list[tuple[str, float]] = []
        for item_id, dist in zip(ids_list, dists):
            # Smaller distance is better. Convert into relevance score.
            relevance = 1.0 / (1.0 + float(dist))
            output.append((item_id, relevance))
        return output

    def _safe_batch_size(self, default: int) -> int:
        if not self.available:
            return default

        try:
            # Chroma exposes this on the client in newer versions.
            dynamic_limit = int(self.collection._client.get_max_batch_size())  # type: ignore[attr-defined]
            return max(1, min(default, dynamic_limit))
        except Exception:
            return default
