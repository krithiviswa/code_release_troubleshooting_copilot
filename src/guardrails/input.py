"""Input guardrails for the engineer's incident description.

WHAT THIS CHECKS (in order):
    1. Basic shape - not empty, not absurdly long.
    2. Prompt injection - an attempt to override the copilot's own instructions.
       Broadened from the original single-pattern regex to cover more of the
       common jailbreak/override phrasings.
    3. Secrets/credentials - redacted (not blocked), so a real incident report
       that happens to include a leaked key can still be processed safely.
    4. PII (email, phone) - redacted for the same reason.
    5. Scope - advisory only. This copilot is scoped to deployment/release
       troubleshooting; input that looks unrelated is flagged in the trace so
       it's visible in telemetry, but not hard-blocked, since a legitimate
       incident can be phrased in ways a keyword heuristic won't recognize.

CHANGE FROM THE ORIGINAL check_input(): now returns a 3-tuple
(block_reason, sanitized_text, warnings) instead of just a block reason,
since the function now also sanitizes rather than only validating. Every
call site was updated to match (src/graph/workflow.py).
"""
from __future__ import annotations

import re

from config import MAX_INPUT_CHARS
from src.guardrails.pii import redact_pii
from src.guardrails.secrets import redact_secrets

INJECTION_PATTERNS = re.compile(
    r"(?i)\b("
    r"ignore (?:all |the )?(?:previous|above|prior) instructions"
    r"|disregard (?:all |the )?(?:previous|above|prior) instructions"
    r"|reveal (?:the )?(?:system )?prompt"
    r"|print (?:the )?(?:system )?prompt"
    r"|you are now"
    r"|act as (?:if you were|a) "
    r"|developer message"
    r"|new instructions?:"
    r"|forget (?:everything|all) (?:you (?:were|are) told|above)"
    r"|do anything now"
    r"|jailbreak"
    r")\b"
)

# PURPOSE: Advisory scope check. Any one of these being present is enough to
# treat the input as in-scope; intentionally permissive (OR, not AND) so we
# flag only clearly off-topic input, not just unusually-phrased input.
_SCOPE_KEYWORDS = re.compile(
    r"(?i)\b("
    r"deploy|deployment|release|rollback|rollout|environment|prod|staging|sit|uat|pt\b|lle\b"
    r"|artifact|build|ticket|jvm|server|cluster|health check|readiness|pipeline"
    r"|kafka|cassandra|solr|database|db\b|certificate|tls|ssl|config|credential"
    r"|xlr|ansible|ci/?cd|incident|outage|traffic|routing|version"
    r")\b"
)


def check_input(text: str) -> tuple[str | None, str, list[str]]:
    """Validate and sanitize the latest engineer submission.

    Returns (block_reason_or_None, sanitized_text, advisory_warnings). When
    block_reason is not None, sanitized_text/advisory_warnings should be
    ignored - the turn is rejected outright.

    NEXT:
        src/graph/workflow.py -> validate_input_node().
    """
    cleaned = (text or "").strip()

    if len(cleaned) < 10:
        return "Please provide a current engineering problem or triage conversation.", "", []

    if len(cleaned) > MAX_INPUT_CHARS:
        return f"Input is too large. Keep the input within {MAX_INPUT_CHARS:,} characters.", "", []

    if INJECTION_PATTERNS.search(cleaned):
        return (
            "The pasted content appears to contain an attempt to change the copilot instructions, "
            "so it was not processed.",
            "",
            [],
        )

    sanitized, secret_hits = redact_secrets(cleaned)
    warnings: list[str] = []
    if secret_hits:
        warnings.append(
            f"Redacted {len(secret_hits)} apparent credential(s) from input before processing: "
            f"{', '.join(secret_hits)}."
        )

    sanitized, pii_hits = redact_pii(sanitized)
    if pii_hits:
        warnings.append(
            f"Redacted apparent personal data from input before processing: {', '.join(pii_hits)}."
        )

    if not _SCOPE_KEYWORDS.search(sanitized):
        warnings.append(
            "Input does not clearly reference deployment/release troubleshooting terminology; "
            "this copilot is scoped to that domain, so the answer may be low quality."
        )

    return None, sanitized, warnings
