"""End-to-end internal RAG pipeline.

BEGINNER FLOW
-------------
multiple queries
    -> Chroma dense search + BM25 keyword search
    -> RRF fusion for each query
    -> RRF again across query variants
    -> CrossEncoder reranking
    -> final evidence
"""
from __future__ import annotations

from pathlib import Path

from config import (
    BM25_CANDIDATE_K,
    CHROMA_DIR,
    CHROMA_COLLECTION,
    DENSE_CANDIDATE_K,
    FINAL_K,
    RRF_K,
)
from src.rag.chunking import chunk_records
from src.rag.embedding import get_embedder
from src.rag.fusion import reciprocal_rank_fusion
from src.rag.ingestion import load_knowledge
from src.rag.reranking import CrossEncoderReranker
from src.rag.retrieval import BM25Retriever, DenseRetriever
from src.rag.store import ChromaStore


class HybridRAG:
    """Runtime retriever for the persisted internal engineering knowledge base."""

    def __init__(self, persist_dir: str | Path = CHROMA_DIR):
        # PURPOSE: Connect to the already-built Chroma collection.
        self.store = ChromaStore(persist_dir)
        self.collection = self.store.collection
        self.records: list[dict] = []
        self.dense = DenseRetriever()
        self.bm25: BM25Retriever | None = None
        # Lazy-load the CrossEncoder only when retrieval is actually used.
        self.reranker: CrossEncoderReranker | None = None

    def build_index(self, records: list[dict], reset: bool = True) -> int:
        """Build the offline vector index from logical records.

        NEXT: scripts/build_index.py -> prints indexed chunk count.
        """
        # PURPOSE: Convert logical records into document-aware retrieval chunks.
        chunks = chunk_records(records)
        if reset:
            self.store.reset()

        # PURPOSE: Convert each chunk into a numerical embedding.
        texts = [item["content"] for item in chunks]
        embeddings = get_embedder().encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()

        # PURPOSE: Persist text, metadata and embeddings in Chroma.
        self.store.add(chunks, embeddings)
        return len(chunks)

    def load_existing_index(self) -> None:
        """Load the persisted chunks so dense retrieval and BM25 can operate.

        NEXT: src/graph/workflow.py -> internal_knowledge_worker().
        """
        self.records = self.store.load_all()
        if not self.records:
            raise RuntimeError(
                f"Chroma collection '{CHROMA_COLLECTION}' is empty. Run scripts/build_index.py first."
            )
        self.bm25 = BM25Retriever(self.records)
        self.reranker = CrossEncoderReranker()

    def dense_search(self, query: str, top_k: int = DENSE_CANDIDATE_K) -> list[dict]:
        """Run semantic retrieval only.

        NEXT: retrieve_and_rerank_many().
        """
        return self.dense.search(self.collection, query, len(self.records), top_k)

    def bm25_search(self, query: str, top_k: int = BM25_CANDIDATE_K) -> list[dict]:
        """Run keyword retrieval only.

        NEXT: retrieve_and_rerank_many().
        """
        if self.bm25 is None:
            return []
        return self.bm25.search(query, top_k)

    def retrieve_and_rerank_many(
        self,
        queries: list[str],
        candidate_k: int = max(DENSE_CANDIDATE_K, BM25_CANDIDATE_K),
        final_k: int = FINAL_K,
    ) -> list[dict]:
        """Run multi-query hybrid retrieval and rerank the merged candidates.

        NEXT: src/mcp_server.py -> search_knowledge().
        """
        clean_queries = list(dict.fromkeys(q.strip() for q in queries if q and q.strip()))
        if not clean_queries:
            return []
        if not self.records:
            self.load_existing_index()

        # PURPOSE: For each query, retrieve with two different methods.
        per_query_rankings: list[list[dict]] = []
        for query in clean_queries:
            dense_results = self.dense_search(query, min(candidate_k, DENSE_CANDIDATE_K))
            bm25_results = self.bm25_search(query, min(candidate_k, BM25_CANDIDATE_K))

            # PURPOSE: Combine the two rankings without comparing raw dense/BM25 scores.
            fused = reciprocal_rank_fusion([dense_results, bm25_results], k=RRF_K)
            per_query_rankings.append(fused)

        # PURPOSE: A user/LLM may have several search views. Fuse those result rankings too.
        fused_across_queries = reciprocal_rank_fusion(per_query_rankings, k=RRF_K)

        # PURPOSE: Final semantic ranking over the candidate pool.
        if self.reranker is None:
            self.reranker = CrossEncoderReranker()
        return self.reranker.rerank(clean_queries, fused_across_queries, final_k)


def get_runtime_rag(persist_dir: str | Path = CHROMA_DIR) -> HybridRAG:
    """Create a runtime-only RAG object from an existing offline index.

    NEXT: src/mcp_server.py -> search_knowledge().
    """
    rag = HybridRAG(persist_dir)
    rag.load_existing_index()
    return rag


def build_index(data_dir: str | Path = "data", persist_dir: str | Path = CHROMA_DIR, reset: bool = True) -> int:
    """Offline entry point: files -> records -> chunks -> embeddings -> Chroma.

    NEXT: scripts/build_index.py -> prints completion message.
    """
    records = load_knowledge(data_dir)
    rag = HybridRAG(persist_dir)
    count = rag.build_index(records, reset=reset)
    print(f"Loaded {len(records)} logical records and indexed {count} chunks.")
    return count
