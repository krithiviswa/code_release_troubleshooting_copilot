"""Document-aware chunking for runbooks, continuous conversations and JIRA tickets.

BEGINNER IDEA
--------------
There is no single perfect chunking strategy.  We preserve each source's natural
boundaries first, then use a standard recursive splitter only when a logical unit
is too large.

Strategies used here:
- Runbook: heading/section-aware, then RecursiveCharacterTextSplitter.
- JIRA: ticket-aware in ingestion, then RecursiveCharacterTextSplitter.
- Triage conversations: message-block-aware, then recursive fallback for one huge message.
"""
from __future__ import annotations

import re


from config import (
    CHUNK_MAX_CHARS,
    CHUNK_MIN_CHARS,
    CHUNK_OVERLAP_CHARS,
    CONVERSATION_OVERLAP_BLOCKS,
)


# PURPOSE: The normal path uses LangChain's standard RecursiveCharacterTextSplitter.
# The object is loaded lazily so lightweight unit tests do not need the large RAG stack at import time.
_TEXT_SPLITTER = None


def _get_text_splitter():
    """Return the configured recursive splitter, with a tiny fallback for dependency-light tests.

    NEXT: _chunk_conversation() or chunk_records().
    """
    global _TEXT_SPLITTER
    if _TEXT_SPLITTER is not None:
        return _TEXT_SPLITTER

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        _TEXT_SPLITTER = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_MAX_CHARS,
            chunk_overlap=CHUNK_OVERLAP_CHARS,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
    except ImportError:
        # FALLBACK: keeps unit tests/imports usable before `pip install -r requirements.txt`.
        class SimpleSplitter:
            def split_text(self, text: str) -> list[str]:
                text = text.strip()
                if len(text) <= CHUNK_MAX_CHARS:
                    return [text] if text else []
                out = []
                step = max(1, CHUNK_MAX_CHARS - CHUNK_OVERLAP_CHARS)
                start = 0
                while start < len(text):
                    end = min(len(text), start + CHUNK_MAX_CHARS)
                    out.append(text[start:end].strip())
                    if end >= len(text):
                        break
                    start += step
                return out

        _TEXT_SPLITTER = SimpleSplitter()

    return _TEXT_SPLITTER


def _message_blocks(text: str) -> list[str]:
    """Split continuous conversation history on blank-line message boundaries.

    WHY: A speaker's message should remain intact where possible.
    NEXT: _chunk_conversation().
    """
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def _merge_tiny_last_chunk(chunks: list[str]) -> list[str]:
    """Avoid leaving a very small final orphan when it can be merged safely.

    NEXT: _chunk_conversation() or chunk_records().
    """
    if len(chunks) <= 1 or len(chunks[-1]) >= CHUNK_MIN_CHARS:
        return chunks

    merged = f"{chunks[-2]}\n\n{chunks[-1]}".strip()
    if len(merged) <= CHUNK_MAX_CHARS:
        return chunks[:-2] + [merged]
    return chunks


def _chunk_conversation(text: str) -> list[str]:
    """Build chunks from whole message blocks with configurable block overlap.

    Example:
        Chunk 1 = messages 1-8
        Chunk 2 = messages 8-15   # message 8 overlaps

    WHY: This preserves conversational context better than cutting at character 1800.
    """
    blocks = _message_blocks(text)
    if not blocks:
        return []

    chunks: list[str] = []
    current: list[str] = []
    index = 0

    while index < len(blocks):
        block = blocks[index]

        # PURPOSE: If one message is itself too large, use the standard recursive fallback.
        if len(block) > CHUNK_MAX_CHARS and not current:
            chunks.extend(_get_text_splitter().split_text(block))
            index += 1
            continue

        candidate = "\n\n".join(current + [block])
        if current and len(candidate) > CHUNK_MAX_CHARS:
            chunks.append("\n\n".join(current).strip())
            # PURPOSE: Repeat a small number of complete message blocks, not arbitrary characters.
            overlap = current[-CONVERSATION_OVERLAP_BLOCKS:] if CONVERSATION_OVERLAP_BLOCKS else []
            current = list(overlap)
            continue

        current.append(block)
        index += 1

    if current:
        chunks.append("\n\n".join(current).strip())

    return _merge_tiny_last_chunk([chunk for chunk in chunks if chunk])


def chunk_records(records: list[dict]) -> list[dict]:
    """Create retrieval chunks and generate unique provenance metadata dynamically.

    NEXT: src/rag/embedding.py -> get_embedder().encode().
    """
    output: list[dict] = []

    for record_index, record in enumerate(records):
        metadata = dict(record["metadata"])
        source_type = metadata.get("source_type", "unknown")

        # PURPOSE: Choose the strategy based on the document shape.
        if source_type == "triage_conversation":
            parts = _chunk_conversation(record["content"])
        else:
            # Runbook and JIRA logical records were already separated by headings in ingestion.
            parts = _get_text_splitter().split_text(record["content"])

        parent_source = str(metadata.get("source_id", f"record-{record_index:04d}"))
        for chunk_index, part in enumerate(parts):
            chunk_id = f"{parent_source}::chunk-{chunk_index:04d}"
            chunk_metadata = dict(metadata)
            chunk_metadata.update(
                {
                    "parent_record_index": str(record_index),
                    "parent_source_id": parent_source,
                    "chunk_index": str(chunk_index),
                    # PURPOSE: source_id points to this exact chunk for citation/provenance.
                    "source_id": chunk_id,
                }
            )
            output.append(
                {
                    "id": chunk_id,
                    "content": part,
                    "metadata": chunk_metadata,
                }
            )

    return output
