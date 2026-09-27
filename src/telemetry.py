"""Lightweight local telemetry, complementary to LangSmith.

WHY THIS EXISTS ALONGSIDE LANGSMITH:
    LangSmith (config.LANGSMITH_ENABLED) gives rich, hosted traces but needs
    an account, an API key, and outbound network access. This module gives a
    zero-dependency, always-available local record of the same underlying
    events (every LLM call, every MCP call) as newline-delimited JSON, so
    token/latency history is inspectable offline - which matters in this
    project's Colab-with-restricted-network setting.

    This is intentionally NOT a replacement for LangSmith's tracing UI - it's
    a durable, greppable log for local debugging and for feeding the
    evaluation harness's telemetry summaries, not a substitute for step-by-
    step trace visualization.

WHAT IT LOGS:
    One JSON line per event, each carrying: event type ("llm_call" or
    "mcp_call"), a UTC timestamp, and whatever usage/timing dict the caller
    already computed (see src/llm.py::invoke_structured, src/mcp_client.py).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock

from config import ENABLE_LOCAL_TELEMETRY, TELEMETRY_LOG_PATH

_write_lock = Lock()


def log_event(event_type: str, payload: dict) -> None:
    """Append one telemetry event as a JSON line, if local telemetry is enabled.

    WHY A THREAD LOCK: specialist workers run concurrently via LangGraph's
    Send(), so more than one event can be logged at close to the same time;
    the lock keeps each JSON line intact rather than interleaved.

    NEXT: called from src/llm.py::invoke_structured() and
    src/mcp_client.py::call_mcp_tool().
    """
    if not ENABLE_LOCAL_TELEMETRY:
        return

    record = {
        "event": event_type,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **payload,
    }

    try:
        path = Path(TELEMETRY_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with _write_lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        # PURPOSE: Telemetry must never break the actual workflow. A failed
        # write (disk full, permissions) is silently dropped rather than
        # raised, exactly like a logging call would be treated.
        pass


def read_recent(limit: int = 50) -> list[dict]:
    """Return the most recent telemetry events, newest last.

    Used for a quick local sanity check (e.g. in a notebook cell) without
    needing a LangSmith account: `from src.telemetry import read_recent`.
    """
    path = Path(TELEMETRY_LOG_PATH)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    events = []
    for line in lines[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
