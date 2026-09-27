"""Embedding model loader used by both indexing and dense retrieval."""
from __future__ import annotations

from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL

_model = None


def get_embedder() -> SentenceTransformer:
    """Load the embedding model once and reuse it in the process.

    WHY: Loading a transformer repeatedly is slow and unnecessary.
    NEXT: src/rag/store.py -> ChromaStore.add() for offline indexing, or
          src/rag/retrieval.py -> DenseRetriever.search() for runtime queries.
    """
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model
