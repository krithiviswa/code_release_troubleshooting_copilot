"""Main LangGraph workflow.

FINAL ARCHITECTURE
------------------
Engineer input
    -> Input Guard
    -> LLM1 Context Understanding
    -> Memory Recall
    -> Planner / Orchestrator
    -> dynamic Internal/External workers via Send()
    -> ReAct clarification decision
    -> optional clarification interrupt -> LLM1 again
    -> Recommendation Agent (LLM3)
    -> Critic / Revision
    -> Output Guard
    -> Memory Write
    -> END

BEGINNER IDEA
--------------
LangGraph is the traffic controller.  It moves a shared CopilotState between
nodes.  LLMs think inside selected nodes; MCP provides the two tools.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from config import (
    AVAILABLE_TOOLS,
    DEFAULT_ENGINEER_ID,
    FINAL_K,
    MAX_CLARIFICATIONS,
    MAX_MCP_CALLS,
    MAX_DYNAMIC_WORKERS,
    MAX_EXTERNAL_QUERIES,
    MAX_EVIDENCE_ITEMS,
    MAX_REFLECTION_ROUNDS,
    MAX_REACT_STEPS,
    MAX_RETRIEVAL_QUERIES,
    MEMORY_TOP_K,
)
from src.agents import critique, decide_react, plan_research, recommend, understand_context
from src.guardrails.evidence import sanitize_evidence
from src.guardrails.input import check_input
from src.guardrails.output import validate_recommendation_citations
from src.mcp_client import call_mcp_tool
from src.memory.store import MemoryStore
from src.schemas import AgentSpec, QueryContext
from src.skills.loader import load_skill
from src.state import CopilotState

# PURPOSE: Persistent memory is separate from LangGraph checkpointing.
# Checkpointing remembers workflow state; this store remembers durable engineer facts.
_memory_store = MemoryStore()


def _dedupe_evidence(evidence: list[dict]) -> list[dict]:
    """Keep one evidence item per ID so duplicate evidence does not bloat prompts.

    NEXT: recommendation_agent_node() or react_controller_node().
    """
    output: list[dict] = []
    seen: set[str] = set()
    for item in evidence:
        key = str(item.get("id") or item.get("chunk_id") or json.dumps(item, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
        if len(output) >= MAX_EVIDENCE_ITEMS:
            break
    return output


def _history_text(turn_history: list[str], latest: str) -> str:
    """Create the text given to LLM1, including all checkpointed human turns.

    WHY: A clarification response may contain more information than the question asked for.
    LLM1 therefore re-understands the entire human history every time the engineer responds.
    """
    turns = list(turn_history)
    if not turns and latest:
        turns = [latest]
    parts = [f"TURN {index}:\n{value}" for index, value in enumerate(turns, start=1)]
    return "\n\n---\n\n".join(parts)


def validate_input_node(state: CopilotState) -> dict:
    """Validate the latest engineer submission and create/append the turn number.

    CALLS:
        src/guardrails/input.py -> check_input().

    NEXT:
        route_after_input() -> context_understanding_node() or blocked_node().
    """
    text = state.get("user_input", "")
    error, sanitized, warnings = check_input(text)
    if error:
        return {"input_error": error, "trace": ["Input Guard: blocked invalid input"]}

    turn_number = int(state.get("turn_number", 0)) + 1
    trace = [f"Input Guard: accepted engineer input as turn {turn_number}"]
    trace.extend(f"Input Guard: {w}" for w in warnings)
    return {
        "input_error": "",
        "turn_number": turn_number,
        # NOTE: store the sanitized (secret/PII-redacted) text, not the raw
        # text, so a leaked credential or email never reaches turn_history,
        # embeddings, or the LangGraph checkpoint on disk.
        "turn_history": [sanitized],
        "guardrail_warnings": warnings,
        "trace": trace,
    }


def route_after_input(state: CopilotState) -> Literal["blocked", "context_understanding"]:
    """Choose the first graph node after input validation.

    NEXT:
        blocked_node() OR context_understanding_node().
    """
    return "blocked" if state.get("input_error") else "context_understanding"


def blocked_node(state: CopilotState) -> dict:
    """Return a safe structured message when input validation fails.

    NEXT: END.
    """
    return {
        "recommendation": {
            "possible_issue_category": "blocked_input",
            "next_steps": [],
            "clarification_questions": [state.get("input_error", "Request blocked.")],
            "clarification_questions_required": True,
        },
        "trace": ["Workflow stopped at Input Guard"],
    }


def context_understanding_node(state: CopilotState) -> dict:
    """LLM1: re-understand all human input, including any new clarification response.

    READS:
        state.turn_history + state.user_input.

    CALLS:
        src/agents.py -> understand_context() -> LLM1.

    WRITES:
        state.context + LLM telemetry.

    NEXT:
        memory_recall_node().
    """
    history = _history_text(state.get("turn_history", []), state.get("user_input", ""))
    call = understand_context(history)
    context = call.output.model_dump()

    # PURPOSE: Protect the downstream graph from an unexpectedly large model response.
    context["retrieval_queries"] = context.get("retrieval_queries", [])[:MAX_RETRIEVAL_QUERIES]

    return {
        "context": context,
        "llm_usage": [call.usage],
        "trace": ["Context Understanding Agent: understand_context() -> LLM1 -> QueryContext"],
    }


def memory_recall_node(state: CopilotState) -> dict:
    """Search persistent engineer memory before planning.

    SIMPLE MEANING:
        Look in the engineer's long-term notebook for useful facts from prior conversations.

    IMPORTANT:
        This is NOT another LLM call.  It is an SQLite FTS search.

    NEXT:
        planner_node().
    """
    engineer_id = state.get("engineer_id", DEFAULT_ENGINEER_ID)
    context = state.get("context", {})
    people = context.get("people_mentioned", [])
    names = " ".join(str(p.get("name", "")) for p in people)
    teams = " ".join(str(p.get("team", "")) for p in people if p.get("team"))

    query = " ".join(
        part
        for part in [
            context.get("current_problem", ""),
            context.get("conversation_summary", ""),
            " ".join(context.get("retrieval_queries", [])),
            names,
            teams,
        ]
        if part
    )

    memories = _memory_store.search(engineer_id, query, top_k=MEMORY_TOP_K)
    return {
        "memory": memories,
        "trace": [f"Memory Recall: {len(memories)} relevant stored fact(s) found"],
    }


def planner_node(state: CopilotState) -> dict:
    """Planner/Orchestrator LLM: select the needed research workers.

    CALLS:
        src/agents.py -> plan_research() -> Planner LLM.

    NEXT:
        route_after_planner().
    """
    call = plan_research(state.get("context", {}), state.get("memory", []), AVAILABLE_TOOLS)

    # PURPOSE: Sanitize the model's plan against the capabilities the application actually exposes.
    safe_specs: list[dict] = []
    seen_roles: set[str] = set()
    fallback_queries = state.get("context", {}).get("retrieval_queries", [])[:MAX_RETRIEVAL_QUERIES]

    for spec in call.output.selected_workers:
        if spec.role in seen_roles:
            continue
        queries = [q.strip() for q in spec.queries if q.strip()][:MAX_RETRIEVAL_QUERIES]
        if not queries:
            queries = fallback_queries or [state.get("context", {}).get("current_problem", "")]
        safe_specs.append(spec.model_copy(update={"queries": queries}))
        seen_roles.add(spec.role)
        if len(safe_specs) >= MAX_DYNAMIC_WORKERS:
            break

    # PURPOSE: The ReAct clarification gate runs only after planned evidence is gathered.
    # If the Planner unexpectedly returns no workers, use the core internal knowledge worker
    # as a defensive fallback rather than entering ReAct with no evidence.
    if not safe_specs:
        safe_specs = [
            AgentSpec(
                role="internal_knowledge",
                objective="Retrieve relevant internal troubleshooting evidence before evaluating clarification.",
                queries=fallback_queries or [state.get("context", {}).get("current_problem", "")],
            )
        ]

    plan = {
        "selected_workers": [spec.model_dump() for spec in safe_specs],
        "rationale": call.output.rationale,
    }
    return {
        "research_plan": plan,
        "llm_usage": [call.usage],
        "trace": [
            "Planner: plan_research() -> LLM2 -> ResearchPlan",
            f"Planner selected {len(safe_specs)} worker role(s)",
        ],
    }


def _send_payload(state: CopilotState, spec: AgentSpec) -> dict[str, Any]:
    """Create the small state packet sent to one dynamic specialist worker.

    NEXT:
        specialist_worker().
    """
    return {
        "engineer_id": state.get("engineer_id", DEFAULT_ENGINEER_ID),
        "thread_id": state.get("thread_id", ""),
        "context": state.get("context", {}),
        "mcp_calls_so_far": len(state.get("mcp_events", [])),
        "memory": state.get("memory", []),
        "agent_spec": spec.model_dump(),
    }


def route_after_planner(state: CopilotState):
    """Route to the planned specialist workers, with ReAct only as a defensive fallback.

    WHY:
        The planner chooses the research path. Clarification is deliberately not
        evaluated here; it is evaluated by ReAct after the planned evidence is collected.

    NEXT:
        specialist_worker() via Send(), or react_controller_node() if a plan produced no workers.
    """
    plan = state.get("research_plan", {})
    specs = [AgentSpec.model_validate(item) for item in plan.get("selected_workers", [])]
    if not specs:
        return "react_controller"

    return [Send("specialist_worker", _send_payload(state, spec)) for spec in specs]


async def specialist_worker(state: dict) -> dict:
    """Execute one dynamically spawned specialist task.

    There are exactly two worker roles:
        internal_knowledge -> MCP search_knowledge() -> Hybrid RAG
        external_research -> MCP search_web() -> public web evidence

    This node itself does not call another LLM.  The Planner produced the queries,
    and the MCP tool performs the retrieval work.

    NEXT:
        react_controller_node() after all Send() worker branches finish.
    """
    spec = AgentSpec.model_validate(state["agent_spec"])
    skill_name = "internal_knowledge" if spec.role == "internal_knowledge" else "external_research"
    skill = load_skill(skill_name)
    queries = spec.queries[: (MAX_EXTERNAL_QUERIES if spec.role == "external_research" else MAX_RETRIEVAL_QUERIES)]
    results: list[dict] = []
    evidence: list[dict] = []
    mcp_events: list[dict] = []
    worker_success = False

    mcp_calls_so_far = int(state.get("mcp_calls_so_far", 0))
    remaining_mcp_budget = max(0, MAX_MCP_CALLS - mcp_calls_so_far)

    if spec.role == "internal_knowledge":
        # PURPOSE: One MCP call can carry multiple internal queries so RRF can combine them.
        if remaining_mcp_budget <= 0:
            return {
                "research_results": [{"worker_role": spec.role, "objective": spec.objective, "ok": False, "observation": {"error": "mcp_budget_reached"}}],
                "trace": ["Dynamic Worker: MCP budget reached; internal search skipped"],
            }
        observation = await call_mcp_tool(
            "search_knowledge",
            {"queries": queries, "top_k": FINAL_K},
        )
        worker_success = bool(observation.get("ok"))
        mcp_events.append(
            {
                "role": spec.role,
                "tool": "search_knowledge",
                "queries": queries,
                "ok": worker_success,
            }
        )
        results.append(
            {
                "worker_role": spec.role,
                "objective": spec.objective,
                "skill": skill_name,
                "queries": queries,
                "tool": "search_knowledge",
                "observation": observation,
                "ok": worker_success,
            }
        )
        if worker_success:
            data = observation.get("data", [])
            if isinstance(data, list):
                evidence.extend(data)

    else:
        # PURPOSE: Search each external query separately using the queries selected by the Planner.
        for query in queries[:remaining_mcp_budget]:
            observation = await call_mcp_tool(
                "search_web",
                {"query": query},
            )
            ok = bool(observation.get("ok"))
            worker_success = worker_success or ok
            mcp_events.append(
                {
                    "role": spec.role,
                    "tool": "search_web",
                    "query": query,
                    "ok": ok,
                }
            )
            results.append(
                {
                    "worker_role": spec.role,
                    "objective": spec.objective,
                    "skill": skill_name,
                    "queries": [query],
                    "tool": "search_web",
                    "observation": observation,
                    "ok": ok,
                }
            )
            if ok and isinstance(observation.get("data"), list):
                for item in observation["data"]:
                    if item.get("url"):
                        evidence.append(
                            {
                                "id": f"web::{item['url']}",
                                "content": item.get("content", ""),
                                "metadata": {
                                    "source_id": item.get("url", ""),
                                    "source_type": "web",
                                    "title": item.get("title", ""),
                                    "url": item.get("url", ""),
                                },
                            }
                        )

    # PURPOSE: Guard against indirect prompt injection and leaked secrets in
    # whatever came back from the tool call, BEFORE it is merged into state
    # and used by the ReAct controller, the recommendation agent, or the
    # critic. See src/guardrails/evidence.py for why this exists.
    evidence, evidence_warnings = sanitize_evidence(evidence)

    return {
        "research_results": results,
        "evidence": evidence,
        "mcp_events": mcp_events,
        "guardrail_warnings": evidence_warnings,
        "worker_roles_used": [spec.role],
        "react_observations": [
            {
                "worker_role": spec.role,
                "ok": worker_success,
                "evidence_count": len(evidence),
                "queries": queries,
            }
        ],
        "trace": [
            f"Dynamic Worker: {spec.role} -> MCP -> {'success' if worker_success else 'no usable result'}",
        ],
    }


def react_controller_node(state: CopilotState) -> dict:
    """Run one bounded ReAct clarification decision after evidence is gathered.

    ReAct here means: reason over the current context/evidence and decide whether
    the engineer must provide one missing current-case fact before recommendation.

    NEXT:
        route_after_react().
    """
    step = int(state.get("react_step_count", 0))
    if step >= MAX_REACT_STEPS:
        decision = {
            "require_clarification": False,
            "clarification_question": "",
            "reason": "Maximum ReAct steps reached; proceed to recommendation.",
        }
        return {
            "react_decision": decision,
            "trace": ["ReAct: budget reached -> recommendation"],
        }

    available_roles = ["internal_knowledge", "external_research"]
    call = decide_react(
        state.get("context", {}),
        _dedupe_evidence(state.get("evidence", [])),
        state.get("memory", []),
        state.get("react_observations", []),
        available_roles,
        step,
    )
    decision = call.output.model_dump()
    return {
        "react_decision": decision,
        "react_step_count": step + 1,
        "llm_usage": [call.usage],
        "trace": [
            f"ReAct step {step + 1}: "
            f"{'clarification required' if decision.get('require_clarification') else 'proceed to recommendation'}"
        ],
    }


def route_after_react(state: CopilotState):
    """Route the ReAct clarification decision.

    NEXT:
        ask_clarification_node() or recommendation_agent_node().
    """
    decision = state.get("react_decision", {})
    if (
        decision.get("require_clarification")
        and int(state.get("clarification_count", 0)) < MAX_CLARIFICATIONS
    ):
        return "ask_clarification"

    return "recommendation_agent"


def ask_clarification_node(state: CopilotState) -> dict:
    """Pause for engineer input using LangGraph interrupt().

    IMPORTANT:
        After the engineer responds, this node writes the response as a NEW human turn.
        The next edge goes back to context_understanding_node(), so LLM1 re-understands it.

    NEXT:
        src/graph/workflow.py -> context_understanding_node().
    """
    question_text = state.get("react_decision", {}).get("clarification_question", "")
    question_text = question_text or "Please provide the missing information needed to continue."

    # PURPOSE: LangGraph persists the state before waiting for the engineer.
    answer = interrupt(
        {
            "type": "clarification",
            "question": question_text,
            "instruction": "You may answer this question and/or provide any additional relevant information.",
        }
    )

    # PURPOSE: The engineer may respond with more than the asked-for detail, so keep the whole response.
    answer = str(answer).strip()
    error, sanitized_answer, answer_warnings = check_input(answer)
    if error:
        # A second interrupt simply asks for usable input and then this same node resumes again.
        answer = interrupt({"type": "clarification", "question": error})
        answer = str(answer).strip()
        error, sanitized_answer, answer_warnings = check_input(answer)
    answer = sanitized_answer if not error else answer

    new_turn_number = int(state.get("turn_number", 0)) + 1
    return {
        "user_input": answer,
        "turn_number": new_turn_number,
        "turn_history": [answer],
        "guardrail_warnings": answer_warnings,
        "clarification_count": int(state.get("clarification_count", 0)) + 1,
        # Reset per-investigation counters for the new human turn.
        "react_step_count": 0,
        "react_decision": {},
        "research_plan": {},
        "trace": ["Clarification received: routing back to LLM1 context understanding"],
    }


def recommendation_agent_node(state: CopilotState) -> dict:
    """Recommendation Agent (LLM3): turn evidence into the engineer-facing answer.

    NEXT:
        critic_node().
    """
    context = QueryContext.model_validate(state.get("context", {}))
    evidence = _dedupe_evidence(state.get("evidence", []))
    call = recommend(
        context,
        evidence,
        state.get("memory", []),
        state.get("critique"),
        state.get("research_results", []),
        state.get("react_observations", []),
    )
    checked, warnings = validate_recommendation_citations(call.output, evidence)
    return {
        "recommendation": checked.model_dump(),
        "guardrail_warnings": warnings,
        "llm_usage": [call.usage],
        "trace": ["Recommendation Agent: recommend() -> LLM3 -> Recommendation"],
    }


def critic_node(state: CopilotState) -> dict:
    """Critic LLM reviews the draft for material problems.

    NEXT:
        route_after_critic().
    """
    call = critique(
        state.get("context", {}),
        state.get("recommendation", {}),
        _dedupe_evidence(state.get("evidence", [])),
        state.get("memory", []),
    )
    critique_result = call.output.model_dump()
    revisions = int(state.get("revision_count", 0))
    next_revisions = revisions + 1 if critique_result.get("verdict") == "REVISE" else revisions
    return {
        "critique": critique_result,
        "revision_count": next_revisions,
        "llm_usage": [call.usage],
        "trace": [f"Critic: {critique_result['verdict']}"],
    }


def route_after_critic(state: CopilotState) -> Literal["recommendation_agent", "output_guard"]:
    """Loop to recommendation when the critic requests another draft.

    NEXT:
        recommendation_agent_node() for REVISE, otherwise output_guard().
    """
    if state.get("critique", {}).get("verdict") == "REVISE" and int(state.get("revision_count", 0)) <= MAX_REFLECTION_ROUNDS:
        return "recommendation_agent"
    return "output_guard"


def output_guard_node(state: CopilotState) -> dict:
    """Final mechanical provenance validation after the reflection loop.

    NEXT:
        memory_write_node().
    """
    from src.schemas import Recommendation

    recommendation = Recommendation.model_validate(state.get("recommendation", {}))
    checked, warnings = validate_recommendation_citations(
        recommendation,
        _dedupe_evidence(state.get("evidence", [])),
    )
    return {
        "recommendation": checked.model_dump(),
        "guardrail_warnings": warnings,
        "trace": ["Output Guard: final citation/provenance validation"],
    }


def memory_write_node(state: CopilotState) -> dict:
    """Persist durable facts extracted by LLM1 without another LLM call.

    WHY:
        The user asked the system to remember facts such as who said what.
        LLM1 already identified durable facts in QueryContext, so a second memory LLM is unnecessary.

    NEXT:
        END.
    """
    engineer_id = state.get("engineer_id", DEFAULT_ENGINEER_ID)
    facts = state.get("context", {}).get("durable_memory_facts", [])
    payload = [dict(item) for item in facts]
    saved = _memory_store.save(
        engineer_id,
        payload,
        source_turn=int(state.get("turn_number", 0)),
        source_text=_history_text(state.get("turn_history", []), state.get("user_input", ""))[:4000],
    )
    return {
        "trace": [f"Memory Write: attempted to store {len(payload)} durable fact(s); saved {saved}"],
    }


def build_graph(checkpointer=None):
    """Build and compile the LangGraph workflow.

    PURPOSE:
        Convert the node/edge description into an executable graph.

    NEXT:
        src/graph/runtime.py -> checkpointed_graph() or direct graph.invoke/ainvoke().
    """
    graph = StateGraph(CopilotState)

    # Each add_node() creates one named box in the workflow.
    graph.add_node("validate_input", validate_input_node)
    graph.add_node("blocked", blocked_node)
    graph.add_node("context_understanding", context_understanding_node)
    graph.add_node("memory_recall", memory_recall_node)
    graph.add_node("planner", planner_node)
    graph.add_node("ask_clarification", ask_clarification_node)
    graph.add_node("specialist_worker", specialist_worker)
    graph.add_node("react_controller", react_controller_node)
    graph.add_node("recommendation_agent", recommendation_agent_node)
    graph.add_node("critic", critic_node)
    graph.add_node("output_guard", output_guard_node)
    graph.add_node("memory_write", memory_write_node)

    # Sequential flow: START -> input -> context -> memory -> planner.
    graph.add_edge(START, "validate_input")
    graph.add_conditional_edges(
        "validate_input",
        route_after_input,
        {"blocked": "blocked", "context_understanding": "context_understanding"},
    )
    graph.add_edge("blocked", END)
    graph.add_edge("context_understanding", "memory_recall")
    graph.add_edge("memory_recall", "planner")

    # Dynamic planner fan-out using LangGraph Send().
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        ["specialist_worker", "react_controller"],
    )

    # After a human answer, re-run LLM1, exactly as agreed.
    graph.add_edge("ask_clarification", "context_understanding")

    # All dynamic workers write to reducer-backed evidence/results state, then continue to ReAct.
    graph.add_edge("specialist_worker", "react_controller")

    # ReAct either requests missing engineer information or proceeds to recommendation.
    graph.add_conditional_edges(
        "react_controller",
        route_after_react,
        ["ask_clarification", "recommendation_agent"],
    )

    # Recommendation -> Critic -> optional revision -> Output Guard.
    graph.add_edge("recommendation_agent", "critic")
    graph.add_conditional_edges(
        "critic",
        route_after_critic,
        {"recommendation_agent": "recommendation_agent", "output_guard": "output_guard"},
    )
    graph.add_edge("output_guard", "memory_write")
    graph.add_edge("memory_write", END)

    return graph.compile(checkpointer=checkpointer)
