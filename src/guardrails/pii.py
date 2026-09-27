"""Lightweight PII detection for engineer-pasted incident text.

WHAT THIS COVERS:
    Email addresses, phone numbers (loose international pattern), and
    IPv4 addresses. This is deliberately narrow: names are NOT detected here
    (reliable name detection needs an NER model, not a regex, and a false
    positive on a common word is worse than missing a name in this context).

WHY REDACT RATHER THAN BLOCK:
    Same philosophy as secrets.py - a real incident report legitimately
    contains a colleague's email or an internal IP address. Blocking the
    whole submission over that would make the tool unusable for its actual
    job. Redacting keeps the submission usable while keeping raw PII out of
    the LLM prompt, the vector store, and the on-disk checkpoint.
"""
from __future__ import annotations

import re

_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # Loose international phone pattern: optional +, then 7-15 digits with
    # optional separators. Deliberately permissive - see false-positive note below.
    ("phone_number", re.compile(r"(?<![\w.])(?:\+?\d[\d\-. ]{8,14}\d)(?![\w.])")),
    ("ipv4_address", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
]

# PURPOSE: A bare IPv4-shaped number is common and legitimate in this domain
# (server addresses, subnet ranges are exactly the kind of thing an engineer
# needs to share for troubleshooting) - so IP addresses are flagged for
# awareness but not redacted by default. Only email/phone are redacted.
_REDACT_BY_DEFAULT = {"email", "phone_number"}


def scan_for_pii(text: str) -> list[str]:
    """Return the list of PII-pattern names found in text (empty if none)."""
    hits: list[str] = []
    for name, pattern in _PII_PATTERNS:
        if pattern.search(text or ""):
            hits.append(name)
    return hits


def redact_pii(text: str, redact_ips: bool = False) -> tuple[str, list[str]]:
    """Replace matched PII with a fixed placeholder.

    Returns (redacted_text, list_of_pattern_names_found).

    NEXT:
        src/guardrails/input.py -> check_input()
    """
    redacted = text or ""
    found: list[str] = []
    for name, pattern in _PII_PATTERNS:
        if not pattern.search(redacted):
            continue
        found.append(name)
        if name in _REDACT_BY_DEFAULT or (name == "ipv4_address" and redact_ips):
            redacted = pattern.sub(f"[REDACTED_{name.upper()}]", redacted)
    return redacted, found
