"""Mechanical provenance and safety checks applied to the final recommendation.

WHAT THIS CHECKS:
    1. Citation/provenance - every source_id and quote must actually be
       present in the retrieved evidence (original check, unchanged in logic).
    2. Ticket/ID hallucination - any REL-/PAY-/BILL-/JIRA-style ID mentioned
       in free-text fields (next_steps, diagnostic_path) must trace back to
       something present in the evidence, or it's flagged as a possible
       hallucination.
    3. Secret leakage - if a secret pattern somehow made it into evidence
       (e.g. a real, non-mocked web result) and the model echoed it into the
       recommendation, it's redacted here before the response ever reaches
       the user.

CHANGE FROM THE ORIGINAL validate_recommendation_citations(): same
signature and return shape (recommendation, warnings), so this is a
drop-in replacement - tests/test_guardrails.py needs no changes.
"""
from __future__ import annotations

import re

from src.guardrails.secrets import redact_secrets
from src.schemas import Recommendation

_ID_PATTERN = re.compile(r"\b[A-Z]{2,10}-\d{3,6}\b")


def _squash(text: str) -> str:
    """Normalize whitespace/case so a verbatim citation can be checked robustly."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _source_id(item: dict) -> str:
    """Read the generated source ID from an evidence item.

    NEXT: validate_recommendation_citations().
    """
    metadata = item.get("metadata", {})
    return str(metadata.get("source_id") or item.get("id") or item.get("chunk_id") or "unknown")


def _free_text_fields(recommendation: Recommendation) -> list[str]:
    """All human-readable text fields worth scanning for hallucinated IDs."""
    fields = list(recommendation.next_steps) + list(recommendation.diagnostic_path)
    if recommendation.possible_issue_category:
        fields.append(str(recommendation.possible_issue_category))
    return fields


def validate_recommendation_citations(recommendation: Recommendation, evidence: list[dict]) -> tuple[Recommendation, list[str]]:
    """Keep only citations whose source and quote are actually present in
    evidence, flag hallucinated ticket IDs, and redact any leaked secret text.

    WHY: A model may invent a source ID, a quote, or a ticket number that was
    never in the evidence. These are mechanical (non-LLM) checks, so they
    catch that case deterministically rather than relying on the model to
    police itself.

    NEXT:
        src/graph/workflow.py -> output_guard_node().
    """
    source_map = {_source_id(item): item for item in evidence}
    valid_traces = [source for source in recommendation.source_traces if source in source_map]
    warnings: list[str] = []

    if len(valid_traces) != len(recommendation.source_traces):
        warnings.append("Some source_traces did not match retrieved evidence and were removed.")

    valid_citations = []
    for citation in recommendation.citations:
        item = source_map.get(citation.source_id)
        if not item:
            warnings.append(f"Citation source {citation.source_id} was not found in retrieved evidence.")
            continue
        if _squash(citation.quote) not in _squash(item.get("content", "")):
            warnings.append(f"Citation quote for {citation.source_id} could not be verified and was removed.")
            continue
        valid_citations.append(citation)

    if evidence and not valid_citations:
        warnings.append("No verifiable citations survived the provenance check.")

    # --- Ticket/ID hallucination check -------------------------------------
    evidence_text = _squash(" ".join(item.get("content", "") for item in evidence))
    mentioned_ids: set[str] = set()
    for field in _free_text_fields(recommendation):
        mentioned_ids.update(_ID_PATTERN.findall(field or ""))
    unverified_ids = [i for i in mentioned_ids if i.lower() not in evidence_text]
    if unverified_ids:
        warnings.append(
            f"The following IDs appear in the recommendation but not in retrieved evidence "
            f"(possible hallucination): {', '.join(sorted(unverified_ids))}."
        )

    # --- Secret leakage check on final text ---------------------------------
    updates: dict = {"source_traces": valid_traces, "citations": valid_citations}
    redacted_steps, secret_hits_steps = (
        zip(*(redact_secrets(s) for s in recommendation.next_steps)) if recommendation.next_steps else ([], [])
    )
    redacted_path, secret_hits_path = (
        zip(*(redact_secrets(s) for s in recommendation.diagnostic_path)) if recommendation.diagnostic_path else ([], [])
    )
    any_secret_hits = any(secret_hits_steps) or any(secret_hits_path)
    if any_secret_hits:
        updates["next_steps"] = list(redacted_steps)
        updates["diagnostic_path"] = list(redacted_path)
        warnings.append("Redacted apparent credential(s) found in the generated recommendation text.")

    return recommendation.model_copy(update=updates), warnings
