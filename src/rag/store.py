"""Thin Chroma persistence wrapper."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

from config import CHROMA_COLLECTION


class ChromaStore:
    """Store chunks, embeddings and provenance in a persistent Chroma collection."""

    def __init__(self, persist_dir: str | Path):
        # PURPOSE: PersistentClient keeps the vector index on disk between runs.
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection(CHROMA_COLLECTION)

    def reset(self) -> None:
        """Delete the collection so offline builds can start from a clean index.

        NEXT: build_index() -> add().
        """
        try:
            self.client.delete_collection(CHROMA_COLLECTION)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(CHROMA_COLLECTION)

    def add(self, chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> None:
        """Persist chunks and their embeddings.

        NEXT: offline build completes; runtime starts later with load_all().
        """
        if not chunks:
            return
        self.collection.add(
            ids=[item["id"] for item in chunks],
            documents=[item["content"] for item in chunks],
            metadatas=[
                {key: str(value) for key, value in item["metadata"].items()}
                for item in chunks
            ],
            embeddings=embeddings,
        )

    def load_all(self) -> list[dict[str, Any]]:
        """Load all persisted text and metadata for BM25 construction.

        NEXT: src/rag/pipeline.py -> HybridRAG.__init__() creates the BM25 retriever.
        """
        result = self.collection.get(include=["documents", "metadatas"])
        ids = result.get("ids", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        return [
            {
                "id": ids[i],
                "content": documents[i],
                "metadata": metadatas[i] or {},
            }
            for i in range(len(ids))
        ]
