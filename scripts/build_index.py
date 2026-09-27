"""Build the offline internal RAG index.

Run once after the source Markdown changes, and again whenever the knowledge base changes.
"""
from config import CHROMA_DIR, DATA_DIR
from src.rag import build_index


if __name__ == "__main__":
    # NEXT: src/rag/pipeline.py -> build_index().
    count = build_index(DATA_DIR, CHROMA_DIR, reset=True)
    print(f"Offline RAG build complete. Indexed {count} chunks.")
