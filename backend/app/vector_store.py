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

        if chromadb is None:
            return

        client = chromadb.PersistentClient(path=str(persist_path))
        self.collection = client.get_or_create_collection(collection_name)
        self.available = True

    def clear(self) -> None:
        if not self.available:
            return
        ids: list[str] = []
        offset = 0
        while True:
            batch = self.collection.get(include=[], offset=offset, limit=1000)
            batch_ids = batch.get("ids", [])
            if not batch_ids:
                break
            ids.extend(batch_ids)
            offset += len(batch_ids)
        if ids:
            self.collection.delete(ids=ids)

    def upsert(self, ids: list[str], texts: list[str], embeddings: list[list[float]], metadatas: list[dict]) -> None:
        if not self.available or not ids:
            return
        self.collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)

    def query(
        self,
        query_embedding: list[float],
        limit: int,
        where: dict | None = None,
    ) -> list[tuple[str, float]]:
        if not self.available:
            return []
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where,
            include=["distances"],
        )

        ids_list = result.get("ids", [[]])[0]
        dists = result.get("distances", [[]])[0]

        output: list[tuple[str, float]] = []
        for item_id, dist in zip(ids_list, dists):
            # Smaller distance is better. Convert into relevance score.
            relevance = 1.0 / (1.0 + float(dist))
            output.append((item_id, relevance))
        return output
