"""Shared secret/credential detection, used by input, output and evidence guardrails.

WHY A SEPARATE MODULE:
    Engineers paste real incident text into this system - Slack threads, log
    lines, ticket notes. Those routinely contain live credentials (a leaked
    API key in a stack trace, a password typed into a terminal that got
    copied into the incident description). We never want that reaching an
    LLM prompt, a vector store, or a checkpoint on disk - and if a secret
    somehow enters the retrieved evidence (e.g. via a real, non-mocked web
    search result), we never want it echoed back out in a recommendation
    either.

NOTE ON FALSE POSITIVES:
    Deliberately over-inclusive. A false positive here just redacts a
    harmless-looking token; a false negative leaks a real credential. Order
    matters: more specific patterns are listed first so a generic
    "any long token" style rule never gets the chance to swallow a more
    specific match first.
"""
from __future__ import annotations

import re

_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws_secret_key", re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*[A-Za-z0-9/+=]{40}")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("generic_password_assignment", re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{6,}")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{20,}\b")),
]


def scan_for_secrets(text: str) -> list[str]:
    """Return the list of secret-pattern names found in text (empty if none)."""
    hits: list[str] = []
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(text or ""):
            hits.append(name)
    return hits


def redact_secrets(text: str) -> tuple[str, list[str]]:
    """Replace any matched secret with a fixed placeholder.

    Returns (redacted_text, list_of_pattern_names_found).

    NEXT:
        src/guardrails/input.py -> check_input()
        src/guardrails/output.py -> validate_recommendation_citations()
        src/guardrails/evidence.py -> sanitize_evidence()
    """
    redacted = text or ""
    found: list[str] = []
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(redacted):
            found.append(name)
            redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted, found
