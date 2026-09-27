"""CrossEncoder reranking after dense/BM25 fusion."""
from __future__ import annotations

from typing import Sequence

from sentence_transformers import CrossEncoder

from config import RERANKER_MODEL


class CrossEncoderReranker:
    """Use a pretrained CrossEncoder to score query/candidate pairs."""

    def __init__(self, model_name: str = RERANKER_MODEL):
        # PURPOSE: Load the reranker once. It is more expensive than simple keyword scoring.
        self.model = CrossEncoder(model_name)

    def rerank(self, queries: Sequence[str], candidates: list[dict], final_k: int) -> list[dict]:
        """Score each candidate against the combined set of search queries.

        WHY: The CrossEncoder sees the query and candidate text together and can make a
        finer relevance judgement than retrieval alone.

        NEXT: src/rag/pipeline.py -> returns final internal evidence to the MCP tool.
        """
        if not candidates:
            return []

        combined_query = " | ".join(dict.fromkeys(q.strip() for q in queries if q.strip()))
        pairs = [(combined_query, item["content"]) for item in candidates]
        scores = self.model.predict(pairs)

        ranked = []
        for item, score in zip(candidates, scores):
            copy = dict(item)
            copy["reranker_score"] = float(score)
            ranked.append(copy)

        ranked.sort(key=lambda item: item["reranker_score"], reverse=True)
        return ranked[:final_k]
