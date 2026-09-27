"""Reciprocal Rank Fusion (RRF) for combining ranked retrieval results."""
from __future__ import annotations

from typing import Any


def reciprocal_rank_fusion(result_lists: list[list[dict[str, Any]]], k: int = 60) -> list[dict[str, Any]]:
    """Combine several ranked lists using only rank positions.

    BEGINNER EXAMPLE
    -----------------
    Dense says [A, B, C].  BM25 says [B, C, D].
    B appears near the top of both lists, so it receives points from both.

    WHY:
        Dense and BM25 scores live on different numerical scales, so we should
        not simply add their raw scores. RRF converts each rank to a small
        contribution: 1 / (k + rank).

    NEXT:
        src/rag/pipeline.py -> CrossEncoderReranker.rerank().
    """
    merged: dict[str, dict[str, Any]] = {}

    for results in result_lists:
        for rank, item in enumerate(results, start=1):
            chunk_id = str(item["chunk_id"])
            entry = merged.setdefault(chunk_id, dict(item))
            # PURPOSE: A higher-ranked item contributes more RRF points.
            entry["rrf_score"] = entry.get("rrf_score", 0.0) + 1.0 / (k + rank)

    return sorted(merged.values(), key=lambda item: item.get("rrf_score", 0.0), reverse=True)
