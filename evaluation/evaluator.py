"""End-to-end synthetic benchmark runner.

The benchmark runs the real LangGraph application, captures its state/telemetry,
and then applies deterministic metrics plus optional DeepEval LLM judges.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from langgraph.types import Command

from config import EVAL_ENABLE_LLM_JUDGE, EVAL_MAX_CASES, LANGGRAPH_RECURSION_LIMIT
from evaluation.metrics import evaluate_case, summarize


def _build_user_input(case: dict) -> str:
    """Create the same free-form style of input that the real Gradio UI accepts.

    NEXT: run_benchmark() -> graph.ainvoke().
    """
    pieces = [
        f"CURRENT PROBLEM:\n{case.get('current_problem', '')}",
        f"ENVIRONMENT (if known):\n{case.get('environment', '')}",
        f"APPLICATION (if known):\n{case.get('application', '')}",
    ]
    attempted = case.get("actions_already_attempted", [])
    if attempted:
        pieces.append("ACTIONS THE ENGINEER SAYS WERE ALREADY ATTEMPTED:\n" + "\n".join(f"- {x}" for x in attempted))
    conversation = case.get("current_triage_conversation", "")
    if conversation:
        pieces.append("CURRENT / RECENT TRIAGE CONVERSATION:\n" + conversation)
    return "\n\n".join(piece for piece in pieces if piece.strip())


def _interrupt_value(result: dict) -> str | None:
    """Extract a human question from LangGraph's __interrupt__ result.

    NEXT: run_benchmark() may resume with Command(resume=...).
    """
    interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", first)
    if isinstance(value, dict):
        return str(value.get("question") or "Please provide the missing information.")
    return str(value)


async def _run_with_possible_clarification(graph, case: dict, engineer_id: str):
    """Run a case and answer configured clarification prompts when the graph pauses.

    WHY: This lets the benchmark exercise the real checkpoint/resume path.
    """
    thread_id = f"eval-{case['test_id']}"
    graph_config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": LANGGRAPH_RECURSION_LIMIT,
    }

    result = await graph.ainvoke(
        {
            "engineer_id": engineer_id,
            "thread_id": thread_id,
            "user_input": _build_user_input(case),
        },
        config=graph_config,
    )

    # A case may have more than one clarification turn; the ground truth can provide a list of responses.
    responses = list(case.get("clarification_responses", []))
    response_index = 0

    while _interrupt_value(result) is not None and response_index < len(responses):
        answer = responses[response_index]
        response_index += 1
        # IMPORTANT: Command(resume=...) resumes the exact checkpointed thread.
        result = await graph.ainvoke(Command(resume=answer), config=graph_config)

    return result, response_index


async def run_benchmark(graph=None, max_cases: int | None = None, use_llm_judge: bool | None = None):
    """Run the real graph against synthetic cases and return summary + per-case rows.

    NEXT: Gradio Evaluation tab or evaluation/run_eval.py.
    """
    from src.graph.runtime import checkpointed_graph
    from src.memory.store import MemoryStore

    cases = json.loads((Path("data") / "ground_truth.json").read_text(encoding="utf-8"))
    cases = cases[: max_cases if max_cases is not None else EVAL_MAX_CASES]
    judge_enabled = EVAL_ENABLE_LLM_JUDGE if use_llm_judge is None else use_llm_judge

    # PURPOSE: Make external-only/both cases reproducible when no live web key is configured.
    old_mock = os.getenv("MOCK_WEB_SEARCH")
    os.environ["MOCK_WEB_SEARCH"] = "true"

    async def _run(active_graph):
        rows: list[dict] = []

        for case in cases:
            engineer_id = f"eval-{case['test_id']}"
            thread_id = f"eval-{case['test_id']}"

            # PURPOSE: Seed an explicit memory fact only for cases designed to test memory recall.
            if case.get("memory_seed"):
                MemoryStore().save(
                    engineer_id,
                    case["memory_seed"],
                    source_turn=0,
                    source_text="Synthetic evaluation seed",
                )

            started = time.perf_counter()
            state, clarification_responses_used = await _run_with_possible_clarification(
                active_graph,
                case,
                engineer_id,
            )
            latency = time.perf_counter() - started

            # If a case stopped at clarification because no response was supplied, it cannot produce a final recommendation.
            prediction = state.get("recommendation", {})
            evidence = state.get("evidence", [])

            row = evaluate_case(case, prediction, evidence, state)

            usage = state.get("llm_usage", [])
            input_tokens = sum(int(item.get("input_tokens", 0)) for item in usage)
            output_tokens = sum(int(item.get("output_tokens", 0)) for item in usage)
            total_tokens = sum(int(item.get("total_tokens", 0)) for item in usage)
            mcp_calls = len(state.get("mcp_events", []))
            web_calls = sum(1 for item in state.get("mcp_events", []) if item.get("tool") == "search_web")

            row.update(
                {
                    "latency_seconds": round(latency, 3),
                    "mcp_calls": mcp_calls,
                    "evidence_count": len(evidence),
                    "llm_calls": len(usage),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "revision_count": int(state.get("revision_count", 0)),
                    "react_steps": int(state.get("react_step_count", 0)),
                    "memory_hits": len(state.get("memory", [])),
                    "web_calls": web_calls,
                    "turn_number": int(state.get("turn_number", 1)),
                    "clarification_responses_used": clarification_responses_used,
                    "clarification_interrupted": _interrupt_value(state) is not None,
                }
            )

            # OPTIONAL: semantic quality evaluation. It adds LLM calls and therefore cost/latency.
            if judge_enabled and prediction and not prediction.get("blocked"):
                try:
                    from evaluation.llm_judge import judge_case

                    row.update(judge_case(case, prediction, evidence))
                except Exception as exc:
                    row["llm_judge_error"] = f"{type(exc).__name__}: {exc}"

            rows.append(row)

        summary = summarize(rows)

        # Operational summary: these metrics help explain cost/latency of the agentic design.
        def avg(field: str) -> float:
            return round(sum(float(row.get(field, 0)) for row in rows) / len(rows), 3) if rows else 0.0

        summary.update(
            {
                "llm_judge_enabled": judge_enabled,
                "avg_latency_seconds": avg("latency_seconds"),
                "total_input_tokens": sum(int(row.get("input_tokens", 0)) for row in rows),
                "total_output_tokens": sum(int(row.get("output_tokens", 0)) for row in rows),
                "total_tokens": sum(int(row.get("total_tokens", 0)) for row in rows),
                "avg_mcp_calls": avg("mcp_calls"),
                "avg_llm_calls": avg("llm_calls"),
                "avg_react_steps": avg("react_steps"),
                "avg_memory_hits": avg("memory_hits"),
                "avg_web_calls": avg("web_calls"),
                "avg_revisions": avg("revision_count"),
                "avg_evidence_count": avg("evidence_count"),
                "llm_judge_model": next((row.get("judge_model") for row in rows if row.get("judge_model")), None),
            }
        )

        for field in [
            "answer_relevancy_score",
            "faithfulness_score",
            "contextual_relevancy_score",
            "contextual_precision_score",
            "contextual_recall_score",
            "next_action_quality_score",
        ]:
            values = [float(row[field]) for row in rows if field in row]
            if values:
                summary[f"avg_{field}"] = round(sum(values) / len(values), 3)

        return {"summary": summary, "rows": rows}

    try:
        if graph is not None:
            return await _run(graph)
        async with checkpointed_graph() as active_graph:
            return await _run(active_graph)
    finally:
        if old_mock is None:
            os.environ.pop("MOCK_WEB_SEARCH", None)
        else:
            os.environ["MOCK_WEB_SEARCH"] = old_mock
