"""Gradio UI for the Engineering Troubleshooting Copilot.

BEGINNER IDEA
--------------
The UI is only the front door.  It starts or resumes a LangGraph thread and
then displays the state that the graph produced.
"""
from __future__ import annotations

import json
import os

import gradio as gr
from langgraph.types import Command

from config import EVAL_ENABLE_LLM_JUDGE, EVAL_MAX_CASES, MAX_INPUT_CHARS, active_models
from evaluation.evaluator import run_benchmark
from src.graph.runtime import checkpointed_graph


def _format_evidence(evidence: list[dict]) -> str:
    """Format internal and external evidence for human inspection.

    NEXT: _submit() / _resume().
    """
    blocks = []
    for index, item in enumerate(evidence, 1):
        metadata = item.get("metadata", {})
        source_type = metadata.get("source_type", "unknown")
        source_id = metadata.get("source_id") or item.get("id", "unknown")
        blocks.append(
            f"### Evidence {index} — {source_type} — {source_id}\n{item.get('content', '')}"
        )
    return "\n\n---\n\n".join(blocks) or "No evidence returned."


def _interrupt_question(result: dict) -> str:
    """Extract a clarification question from LangGraph's __interrupt__ payload."""
    interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
    if not interrupts:
        return ""
    value = getattr(interrupts[0], "value", interrupts[0])
    if isinstance(value, dict):
        return str(value.get("question", "Please provide the missing information."))
    return str(value)


def _telemetry(state: dict) -> dict:
    """Summarize runtime behavior in beginner-friendly numbers.

    WHY: This lets you see the cost/complexity of a particular graph execution.
    """
    usage = state.get("llm_usage", [])
    return {
        "turn_number": state.get("turn_number", 0),
        "llm_calls": len(usage),
        "input_tokens": sum(int(x.get("input_tokens", 0)) for x in usage),
        "output_tokens": sum(int(x.get("output_tokens", 0)) for x in usage),
        "total_tokens": sum(int(x.get("total_tokens", 0)) for x in usage),
        "llm_latency_seconds": round(sum(float(x.get("latency_seconds", 0)) for x in usage), 3),
        "mcp_calls": len(state.get("mcp_events", [])),
        "workers_used": sorted(set(state.get("worker_roles_used", []))),
        "react_steps": state.get("react_step_count", 0),
        "clarifications": state.get("clarification_count", 0),
        "revisions": state.get("revision_count", 0),
        "memory_hits": len(state.get("memory", [])),
    }


async def _run_graph(initial_state: dict, thread_id: str):
    """Open a checkpointed graph and execute one initial or resumed request.

    NEXT: _submit() or _resume().
    """
    async with checkpointed_graph() as graph:
        return await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )


async def _submit(engineer_id: str, thread_id: str, engineer_input: str):
    """Start a new LangGraph turn from the engineer's free-form input.

    The input can be a single issue OR a pasted history covering days/months.
    """
    engineer_id = engineer_id.strip() or "demo-engineer"
    thread_id = thread_id.strip() or f"thread-{engineer_id}"
    if not engineer_input.strip():
        raise gr.Error("Paste the current problem, current discussion, or recent conversation history.")

    state = await _run_graph(
        {
            "engineer_id": engineer_id,
            "thread_id": thread_id,
            "user_input": engineer_input[:MAX_INPUT_CHARS],
        },
        thread_id,
    )

    return _ui_values(state)


async def _resume(engineer_id: str, thread_id: str, engineer_response: str):
    """Resume a paused clarification thread with the engineer's new response.

    IMPORTANT:
        The graph resumes at the interrupt, then its next edge goes back to LLM1.
        LLM1 therefore re-understands the complete accumulated human history.
    """
    engineer_id = engineer_id.strip() or "demo-engineer"
    thread_id = thread_id.strip() or f"thread-{engineer_id}"
    if not engineer_response.strip():
        raise gr.Error("Please enter the clarification response or any additional information.")

    async with checkpointed_graph() as graph:
        state = await graph.ainvoke(
            Command(resume=engineer_response[:MAX_INPUT_CHARS]),
            config={"configurable": {"thread_id": thread_id}},
        )

    return _ui_values(state)


def _ui_values(state: dict):
    """Convert graph state into Gradio output values."""
    return (
        state.get("recommendation", {}),
        _interrupt_question(state),
        _format_evidence(state.get("evidence", [])),
        json.dumps(state.get("context", {}), indent=2, ensure_ascii=False),
        json.dumps(state.get("memory", []), indent=2, ensure_ascii=False),
        json.dumps(state.get("research_plan", {}), indent=2, ensure_ascii=False),
        json.dumps(state.get("react_observations", []), indent=2, ensure_ascii=False),
        _telemetry(state),
        "\n".join(f"- {item}" for item in state.get("trace", [])),
    )


async def _evaluate(use_llm_judge: bool):
    """Run deterministic + optional DeepEval evaluation and return a table."""
    result = await run_benchmark(max_cases=EVAL_MAX_CASES, use_llm_judge=use_llm_judge)
    columns = [
        "test_id",
        "category_match",
        "next_action_coverage",
        "source_coverage",
        "no_repeat_pass",
        "clarification_match",
        "worker_selection_accuracy",
        "worker_execution_success",
        "memory_match",
        "retrieval_source_recall",
        "retrieval_source_mrr",
        "answer_relevancy_score",
        "faithfulness_score",
        "contextual_relevancy_score",
        "contextual_precision_score",
        "contextual_recall_score",
        "next_action_quality_score",
        "latency_seconds",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "mcp_calls",
        "react_steps",
        "revision_count",
    ]
    table = [[row.get(column) for column in columns] for row in result["rows"]]
    return result["summary"], table


def build_ui():
    """Build the complete Gradio application."""
    models = active_models()
    with gr.Blocks(title="Engineering Troubleshooting Copilot") as demo:
        gr.Markdown(
            "# Engineering Troubleshooting Copilot\n"
            "LangGraph + Planner + two dynamic workers + MCP + Hybrid RAG + ReAct + memory + reflection.\n\n"
            f"**Profile:** {models['profile']} | **Context:** {models['context_model']} | "
            f"**Planner:** {models['planner_model']} | **Recommendation:** {models['recommendation_model']}"
        )

        with gr.Tab("Copilot"):
            with gr.Row():
                engineer_id = gr.Textbox(label="Engineer ID (memory key)", value="demo-engineer")
                thread_id = gr.Textbox(label="Thread ID (checkpoint key)", value="demo-thread")

            engineer_input = gr.Textbox(
                label="Engineer input",
                placeholder=(
                    "Paste a current issue, OR the last 5–10 messy triage conversations. "
                    "You can also ask multiple related questions in one input."
                ),
                lines=25,
            )
            submit = gr.Button("Start / analyze", variant="primary")

            clarification = gr.Textbox(
                label="Clarification requested by the agent",
                interactive=False,
                lines=3,
            )
            engineer_response = gr.Textbox(
                label="Engineer follow-up (answer + any extra context)",
                placeholder="Use this only when the agent asks for clarification.",
                lines=8,
            )
            resume = gr.Button("Continue this thread", variant="secondary")

            with gr.Row():
                recommendation = gr.JSON(label="Recommendation")
                context = gr.Code(label="LLM1 context", language="json")

            evidence = gr.Markdown(label="Internal / external evidence")
            with gr.Row():
                memory = gr.Code(label="Recalled memory", language="json")
                plan = gr.Code(label="Planner research plan", language="json")
            with gr.Row():
                react = gr.Code(label="ReAct observations", language="json")
                telemetry = gr.JSON(label="Runtime telemetry")
            trace = gr.Markdown(label="Workflow trace")

            outputs = [recommendation, clarification, evidence, context, memory, plan, react, telemetry, trace]
            submit.click(fn=_submit, inputs=[engineer_id, thread_id, engineer_input], outputs=outputs)
            resume.click(fn=_resume, inputs=[engineer_id, thread_id, engineer_response], outputs=outputs)

        with gr.Tab("Evaluation"):
            gr.Markdown(
                f"Run the synthetic benchmark (up to {EVAL_MAX_CASES} cases). "
                "Deterministic metrics are always run; DeepEval/G-Eval adds extra judge-model calls."
            )
            use_judge = gr.Checkbox(label="Use DeepEval LLM-as-a-judge", value=EVAL_ENABLE_LLM_JUDGE)
            eval_button = gr.Button("Run evaluation benchmark", variant="primary")
            eval_summary = gr.JSON(label="Evaluation summary")
            eval_table = gr.Dataframe(label="Per-case metrics", interactive=False)
            eval_button.click(fn=_evaluate, inputs=[use_judge], outputs=[eval_summary, eval_table])

    return demo


def launch_app(share: bool = False):
    """Launch Gradio.

    NEXT: end user interacts through the browser.
    """
    return build_ui().launch(share=share)


if __name__ == "__main__":
    launch_app(share=os.getenv("GRADIO_SHARE", "false").lower() == "true")
