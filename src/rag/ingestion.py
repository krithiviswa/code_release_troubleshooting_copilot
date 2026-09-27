"""Offline ingestion: load files and split them into logical records.

IMPORTANT
---------
The Markdown files deliberately do NOT contain application metadata headers.
Metadata used by Chroma is generated here from the file structure and position -
including filtering fields like process/phase/environment, which are INFERRED
dynamically from heading text and section context during ingestion, never
hand-annotated in the source Markdown itself. This keeps the source files
readable as plain prose (a runbook a person would actually read, a chat
transcript that looks like a chat transcript) while still producing rich,
filterable metadata for retrieval.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _clean_lines(text: str) -> str:
    """Normalize spaces while preserving blank lines and line boundaries.

    WHY: Blank lines and speaker boundaries matter for conversation-aware chunking.
    NEXT: split_markdown_records().
    """
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        lines.append(re.sub(r"[ \t]+", " ", line).rstrip())
    return "\n".join(lines).strip()


def _slug(value: str, fallback: str) -> str:
    """Create a stable human-readable identifier from a heading.

    WHY: We need citation IDs even though the source files do not contain metadata headers.
    """
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value[:80] or fallback


# --------------------------------------------------------------------------
# Dynamic metadata inference (NOT read from the Markdown text - computed here)
# --------------------------------------------------------------------------

_PHASE_PATTERN = re.compile(r"(?i)^phase\s+(\d+)\s*[\u2013\-]\s*(.+)$")

# PURPOSE: Environment keywords are matched as whole words against the heading
# AND the record body, so a phase inherits its environment even when only the
# body text mentions it (e.g. "...deploy to the PT environment...").
_ENV_KEYWORDS: list[tuple[str, re.Pattern]] = [
    ("SIT", re.compile(r"\bSIT\b")),
    ("UAT", re.compile(r"\bUAT\b")),
    ("PT", re.compile(r"\bPT\b")),
    ("Prod", re.compile(r"(?i)\bprod(?:uction)?\b")),
    ("LLE", re.compile(r"\bLLE\b")),
]


def _infer_environment(title: str, body: str) -> str:
    """Infer which environment(s) a record concerns, from its own text.

    Returns a single flat scalar string (pipe-joined if more than one match),
    since Chroma metadata values must be flat scalars, not lists.

    NEXT: split_markdown_records().
    """
    haystack = f"{title}\n{body}"
    found = [name for name, pattern in _ENV_KEYWORDS if pattern.search(haystack)]
    return "|".join(found)


def _infer_process(h1_section: str) -> str:
    """Infer which deployment process a record belongs to, from its enclosing H1.

    WHY THIS EXISTS: runbook.md has two H1 sections - the Prod runbook and the
    LLE-via-XLR runbook - and every H2/H3 phase underneath one of them belongs
    to that process. Rather than annotating each phase, we infer it once from
    which H1 section we're currently inside while walking the document.

    NEXT: split_markdown_records().
    """
    lowered = h1_section.lower()
    if "lle" in lowered or "xlr" in lowered:
        return "lle_deployment"
    if "runbook" in lowered:
        return "prod_deployment"
    return ""


def _infer_phase(title: str) -> dict[str, str]:
    """Infer phase_number/phase_name from a "Phase N - ..." style heading.

    NEXT: split_markdown_records().
    """
    match = _PHASE_PATTERN.match(title.strip())
    if not match:
        return {}
    return {"phase_number": match.group(1), "phase_name": _slug(match.group(2), "phase")}


def _dynamic_metadata(title: str, body: str, h1_section: str) -> dict[str, str]:
    """Compute all inferred filtering metadata for one heading-based record.

    NEXT: split_markdown_records().
    """
    meta: dict[str, str] = {}
    process = _infer_process(h1_section)
    if process:
        meta["process"] = process
    environment = _infer_environment(title, body)
    if environment:
        meta["environment"] = environment
    meta.update(_infer_phase(title))
    return meta


def split_markdown_records(text: str, source_name: str) -> list[dict[str, Any]]:
    """Split structured files into logical records and leave conversational
    transcripts continuous.

    STRATEGY
    --------
    - Runbook: use Markdown headings as logical sections. Filtering metadata
      (process/phase/environment) is inferred dynamically per heading - see
      _dynamic_metadata() - never read from an annotation in the text.
    - JIRA: use top-level ticket headings such as '# REL-10245'.
    - Triage conversations: keep the entire continuous history as one logical
      record; the separate chunker splits it on message blocks so an
      artificial incident ID is never introduced into the source file. This
      is also where the realistic, multi-month, named-participant release
      channel transcript lives (data/triageconversations.md) - both the
      routine release execution chatter and the incident triage exchanges
      are the same continuous stream, exactly as a real chat export would be.

    NEXT: src/rag/chunking.py -> chunk_records().
    """
    cleaned = _clean_lines(text)
    source_lower = source_name.lower()

    # PURPOSE: Conversation history is a continuous stream, so don't invent record headers.
    if "triage" in source_lower or "conversation" in source_lower:
        return [
            {
                "content": cleaned,
                "metadata": {
                    "source_type": "triage_conversation",
                    "document_name": source_name,
                    "record_index": "0",
                    "record_title": "continuous_conversation_history",
                    "source_id": "triage::record-0000",
                },
            }
        ] if cleaned else []

    # PURPOSE: Runbook and JIRA have explicit Markdown record boundaries.
    # We accept # / ## / ### headings and use the heading text as a record title.
    matches = list(re.finditer(r"(?m)^(#{1,3})\s+(.+?)\s*$", cleaned))
    base_type = "jira" if "jira" in source_lower else "runbook"

    if not matches:
        return [
            {
                "content": cleaned,
                "metadata": {
                    "source_type": base_type,
                    "document_name": source_name,
                    "record_index": "0",
                    "record_title": source_name,
                    "source_id": f"{base_type}::record-0000",
                },
            }
        ] if cleaned else []

    records: list[dict[str, Any]] = []
    current_h1 = ""

    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()

        # PURPOSE: Track which H1 section we're currently inside, so H2/H3
        # phases underneath it can dynamically infer their process (e.g.
        # "lle_deployment" vs "prod_deployment") without any annotation.
        if level == 1:
            current_h1 = title

        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        block = cleaned[start:end].strip()
        body_lines = block.splitlines()[1:]
        body = "\n".join(body_lines).strip()
        if not body:
            continue

        source_id = f"{base_type}::{_slug(title, f'record-{index:04d}')}"
        record_metadata = {
            "source_type": base_type,
            "document_name": source_name,
            "record_index": str(len(records)),
            "record_title": title,
            "source_id": source_id,
        }
        if base_type == "runbook":
            record_metadata.update(_dynamic_metadata(title, body, current_h1))
        records.append({"content": block, "metadata": record_metadata})

    # If a document has content before the first heading, retain it as a separate record.
    prefix = cleaned[: matches[0].start()].strip()
    if prefix:
        records.insert(
            0,
            {
                "content": prefix,
                "metadata": {
                    "source_type": base_type,
                    "document_name": source_name,
                    "record_index": "prefix",
                    "record_title": f"{source_name}::prefix",
                    "source_id": f"{base_type}::prefix",
                },
            },
        )

    return records


def load_knowledge(data_dir: str | Path = "data") -> list[dict[str, Any]]:
    """Load all three synthetic sources and return logical records.

    NEXT: scripts/build_index.py -> src.rag.pipeline.build_index().
    """
    data_path = Path(data_dir)
    records: list[dict[str, Any]] = []

    for file_name in ["runbook.md", "triageconversations.md", "jiratickets.md"]:
        path = data_path / file_name
        records.extend(split_markdown_records(path.read_text(encoding="utf-8"), file_name))

    return records
