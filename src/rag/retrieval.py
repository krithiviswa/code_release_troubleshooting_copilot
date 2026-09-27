"""Dense and sparse retrieval components for the internal knowledge base."""
from __future__ import annotations

from typing import Any

from rank_bm25 import BM25Okapi

from config import BM25_CANDIDATE_K, DENSE_CANDIDATE_K
from src.rag.embedding import get_embedder


class DenseRetriever:
    """Semantic retriever backed by Chroma vector similarity."""

    def search(self, collection: Any, query: str, record_count: int, top_k: int = DENSE_CANDIDATE_K) -> list[dict]:
        """Encode a query and return nearest chunks from Chroma.

        WHY: Dense retrieval catches meaning even when words differ.
        NEXT: src/rag/fusion.py -> reciprocal_rank_fusion().
        """
        if record_count == 0:
            return []

        # PURPOSE: Convert the natural-language query into an embedding vector.
        query_embedding = get_embedder().encode([query], normalize_embeddings=True).tolist()

        # PURPOSE: Ask Chroma for the nearest vectors. No metadata filter is applied by design.
        result = collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, record_count),
            include=["documents", "metadatas", "distances"],
        )

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        ids = (result.get("ids") or [[]])[0]

        return [
            {
                "chunk_id": ids[i],
                "content": documents[i],
                "metadata": metadatas[i] or {},
                # This is an easy-to-read derived score; RRF does not depend on it.
                "dense_score": 1 / (1 + float(distances[i])),
                "bm25_score": 0.0,
                "rrf_score": 0.0,
                "reranker_score": 0.0,
            }
            for i in range(len(documents))
        ]


class BM25Retriever:
    """Keyword retriever for exact engineering terms such as JVM, DML or EAR."""

    def __init__(self, records: list[dict]):
        # PURPOSE: Store all chunks in memory so BM25 can score them at runtime.
        self.records = records
        # Simple tokenization is enough for the synthetic capstone corpus.
        tokenized = [record["content"].lower().split() for record in records]
        self.bm25 = BM25Okapi(tokenized) if tokenized else None

    def search(self, query: str, top_k: int = BM25_CANDIDATE_K) -> list[dict]:
        """Return chunks ranked by keyword relevance.

        NEXT: src/rag/fusion.py -> reciprocal_rank_fusion().
        """
        if not self.records or self.bm25 is None:
            return []

        scores = self.bm25.get_scores(query.lower().split())
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        return [
            {
                "chunk_id": self.records[i]["id"],
                "content": self.records[i]["content"],
                "metadata": self.records[i]["metadata"],
                "dense_score": 0.0,
                "bm25_score": float(scores[i]),
                "rrf_score": 0.0,
                "reranker_score": 0.0,
            }
            for i in order
        ]
