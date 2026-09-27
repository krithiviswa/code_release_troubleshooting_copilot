"""LLM responsibilities kept separate from graph orchestration.

BEGINNER IDEA
--------------
Each function in this file has one AI responsibility.  The graph decides
WHEN to call these functions; these functions decide WHAT the LLM should do.
"""
from __future__ import annotations

from config import (
    CONTEXT_MODEL,
    CRITIC_MODEL,
    MAX_DYNAMIC_WORKERS,
    MAX_REACT_STEPS,
    MAX_RETRIEVAL_QUERIES,
    PLANNER_MODEL,
    RECOMMENDATION_MODEL,
)
from src.llm import invoke_structured
from src.prompts.critic import critic_prompt
from src.prompts.knowledge import knowledge_prompt
from src.prompts.planner import planner_prompt
from src.prompts.react import react_prompt
from src.prompts.recommendation import recommendation_prompt
from src.schemas import Critique, QueryContext, Recommendation, ReActDecision, ResearchPlan


def understand_context(history_text: str):
    """LLM1: understand the complete human-provided conversation history.

    PURPOSE:
        Turn messy current input plus prior turn history into structured context.

    INPUT:
        The accumulated human turn history, not just the latest sentence.

    CALLS:
        src/llm.py -> invoke_structured() -> CONTEXT_MODEL.

    WRITES:
        QueryContext containing current state, attempted actions, people, gaps and queries.

    NEXT:
        src/graph/workflow.py -> memory_recall_node().
    """
    return invoke_structured(
        CONTEXT_MODEL,
        QueryContext,
        knowledge_prompt(history_text, MAX_RETRIEVAL_QUERIES),
        operation="context_understanding",
    )


def plan_research(context: dict, memory: list[dict], available_tools: list[str]):
    """Planner LLM: choose one or two specialist workers.

    PURPOSE:
        Decide the initial research plan instead of blindly invoking every worker.

    INPUT:
        LLM1 context, recalled memory, and the tools that the application really exposes.

    CALLS:
        src/llm.py -> invoke_structured() -> PLANNER_MODEL.

    WRITES:
        ResearchPlan with selected workers and their queries.

    NEXT:
        src/graph/workflow.py -> route_after_planner().
    """
    return invoke_structured(
        PLANNER_MODEL,
        ResearchPlan,
        planner_prompt(context, memory, MAX_DYNAMIC_WORKERS, available_tools),
        operation="planner",
    )


def decide_react(
    context: dict,
    evidence: list[dict],
    memory: list[dict],
    observations: list[dict],
    available_worker_roles: list[str],
    steps_used: int,
):
    """ReAct controller: decide whether engineer clarification is required after research.

    PURPOSE:
        ReAct means Reason -> Action -> Observation -> Reason again. In this design,
        the action is intentionally bounded to either requiring clarification or
        allowing the workflow to proceed to the Recommendation Agent.

    NEXT:
        src/graph/workflow.py -> route_after_react().
    """
    return invoke_structured(
        PLANNER_MODEL,
        ReActDecision,
        react_prompt(
            context,
            evidence,
            memory,
            observations,
            available_worker_roles,
            steps_used,
            MAX_REACT_STEPS,
        ),
        operation="react_controller",
    )


def recommend(
    context: QueryContext,
    evidence: list[dict],
    memory: list[dict],
    critique: dict | None = None,
    research_results: list[dict] | None = None,
    react_observations: list[dict] | None = None,
):
    """Recommendation Agent (LLM3): produce the structured final answer.

    NEXT:
        src/graph/workflow.py -> critic_node().
    """
    return invoke_structured(
        RECOMMENDATION_MODEL,
        Recommendation,
        recommendation_prompt(
            context.model_dump(),
            evidence,
            memory,
            critique,
            research_results or [],
            react_observations or [],
        ),
        operation="recommendation",
    )


def critique(context: dict, recommendation: dict, evidence: list[dict], memory: list[dict]):
    """Critic LLM: decide whether the draft should PASS or REVISE.

    NEXT:
        src/graph/workflow.py -> route_after_critic().
    """
    return invoke_structured(
        CRITIC_MODEL,
        Critique,
        critic_prompt(context, recommendation, evidence, memory),
        operation="critic",
    )
