"""Shared LangGraph state.

BEGINNER IDEA
--------------
Imagine a shared folder travelling through the graph.  Each node reads some
files from the folder and adds/updates other files.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class CopilotState(TypedDict, total=False):
    """State carried between LangGraph nodes."""

    engineer_id: str
    thread_id: str
    # Latest engineer submission.  The complete turn history is separate below.
    user_input: str
    context: dict[str, Any]
    memory: list[dict]
    # Reducer: append the new human submission rather than replacing old submissions.
    turn_history: Annotated[list[str], operator.add]
    turn_number: int
    research_plan: dict[str, Any]
    # Reducer: multiple Send() workers append their results into the same list.
    research_results: Annotated[list[dict], operator.add]
    # Reducer: remember which specialist roles have actually been invoked in this thread.
    worker_roles_used: Annotated[list[str], operator.add]
    # The current merged evidence set.  Normalized to internal/external evidence only.
    # Reducer: multiple Send() workers (internal_knowledge + external_research) can
    # each write evidence in the same superstep; _dedupe_evidence() cleans up on read.
    evidence: Annotated[list[dict], operator.add]
    react_decision: dict[str, Any]
    react_observations: Annotated[list[dict], operator.add]
    react_step_count: int
    clarification_count: int
    recommendation: dict[str, Any]
    critique: dict[str, Any]
    revision_count: int
    trace: Annotated[list[str], operator.add]
    guardrail_warnings: Annotated[list[str], operator.add]
    input_error: str
    # Reducer: record worker/tool telemetry from parallel branches.
    mcp_events: Annotated[list[dict], operator.add]
    llm_usage: Annotated[list[dict], operator.add]
