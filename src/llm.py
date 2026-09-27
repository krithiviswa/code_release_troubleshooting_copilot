"""One place where application LLM calls happen.

BEGINNER IDEA
--------------
Keeping one wrapper around ChatOpenAI means we can measure latency/tokens in one
place and change model configuration without rewriting every agent.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Type

from langchain_openai import ChatOpenAI

from config import MODEL_TEMPERATURE
from src.telemetry import log_event


@dataclass
class LLMCallResult:
    """The parsed Pydantic output plus telemetry captured for that call."""

    output: Any
    usage: dict


def _extract_usage(response: Any) -> dict:
    """Read provider token metadata when LangChain exposes it.

    WHY: Token counts are useful for comparing model profiles and workflow complexity.
    NEXT: invoke_structured() -> returns LLMCallResult.
    """
    usage = getattr(response, "usage_metadata", None) or {}
    if usage:
        return {
            "input_tokens": int(usage.get("input_tokens", 0) or 0),
            "output_tokens": int(usage.get("output_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
        }

    metadata = getattr(response, "response_metadata", None) or {}
    token_usage = metadata.get("token_usage", {}) or metadata.get("usage", {}) or {}
    input_tokens = token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0))
    output_tokens = token_usage.get("completion_tokens", token_usage.get("output_tokens", 0))
    total_tokens = token_usage.get("total_tokens", 0)
    return {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int(total_tokens or 0),
    }


def invoke_structured(model_name: str, schema: Type, prompt: str, operation: str) -> LLMCallResult:
    """Call an LLM and require output that matches a Pydantic schema.

    PURPOSE:
        Give an agent a predictable structured result instead of arbitrary prose.

    READS:
        model_name, schema, prompt.

    CALLS:
        langchain_openai.ChatOpenAI.invoke().

    WRITES:
        Returns parsed schema + latency/token telemetry.

    NEXT:
        src/agents.py -> the operation-specific agent function.
    """
    started = time.perf_counter()

    # PURPOSE: Create the model selected through config.py.
    model_kwargs = {"model": model_name}
    # PURPOSE: Only send temperature when explicitly configured. Newer reasoning models
    # may reject temperature under non-none reasoning modes.
    if MODEL_TEMPERATURE is not None:
        model_kwargs["temperature"] = MODEL_TEMPERATURE
    model = ChatOpenAI(**model_kwargs)

    # PURPOSE: Ask the provider/framework to parse the answer into our Pydantic schema.
    bundle = model.with_structured_output(schema, include_raw=True).invoke(prompt)

    raw = bundle.get("raw") if isinstance(bundle, dict) else bundle
    parsed = bundle.get("parsed") if isinstance(bundle, dict) else bundle

    usage = _extract_usage(raw)
    usage.update(
        {
            "operation": operation,
            "model": model_name,
            "latency_seconds": round(time.perf_counter() - started, 3),
        }
    )

    log_event("llm_call", usage)

    return LLMCallResult(output=parsed, usage=usage)
