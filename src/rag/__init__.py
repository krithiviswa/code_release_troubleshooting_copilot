"""Convenience exports for the internal RAG package.

Heavy runtime dependencies are imported only by the functions that need them.
"""
from src.rag.chunking import chunk_records
from src.rag.ingestion import load_knowledge, split_markdown_records


def build_index(*args, **kwargs):
    """Lazy wrapper around the offline RAG builder.

    NEXT: scripts/build_index.py -> this function -> src/rag/pipeline.py::build_index().
    """
    from src.rag.pipeline import build_index as _build_index
    return _build_index(*args, **kwargs)


def get_runtime_rag(*args, **kwargs):
    """Lazy wrapper around the runtime RAG loader.

    NEXT: src/mcp_server.py::search_knowledge().
    """
    from src.rag.pipeline import get_runtime_rag as _get_runtime_rag
    return _get_runtime_rag(*args, **kwargs)


__all__ = [
    "build_index", "get_runtime_rag", "load_knowledge", "split_markdown_records", "chunk_records"
]
