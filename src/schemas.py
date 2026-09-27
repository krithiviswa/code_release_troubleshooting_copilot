"""Pydantic contracts used by LLM calls and important workflow decisions.

BEGINNER IDEA
--------------
A schema is a shape.  Instead of letting the model return arbitrary prose,
we tell it the fields we expect so the next Python method knows what to read.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class PersonMention(BaseModel):
    """A person explicitly mentioned in the engineer's input."""

    name: str
    role: Optional[str] = None
    team: Optional[str] = None


class MemoryFactInput(BaseModel):
    """A durable fact that should be remembered about an engineer's context."""

    fact: str = Field(min_length=5, max_length=1000)
    person: Optional[str] = None
    team: Optional[str] = None
    topic: Optional[str] = None
    importance: Literal["low", "medium", "high"] = "medium"


class QueryContext(BaseModel):
    """LLM1 output: what is happening now and what information should be searched."""

    current_problem: str
    environment: Optional[str] = None
    application: Optional[str] = None
    issue_category: Optional[str] = None
    conversation_summary: str = ""
    actions_already_attempted: list[str] = Field(default_factory=list)
    people_mentioned: list[PersonMention] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)
    user_questions: list[str] = Field(default_factory=list, max_length=8)
    retrieval_queries: list[str] = Field(default_factory=list, max_length=5)
    durable_memory_facts: list[MemoryFactInput] = Field(default_factory=list, max_length=5)


class AgentSpec(BaseModel):
    """One specialist task the planner can dynamically spawn with Send()."""

    role: Literal["internal_knowledge", "external_research"]
    objective: str = Field(min_length=1, max_length=1500)
    queries: list[str] = Field(default_factory=list, max_length=5)


class ResearchPlan(BaseModel):
    """Planner output: one or two specialist research tasks."""

    selected_workers: list[AgentSpec] = Field(default_factory=list, max_length=2)
    rationale: str = ""


class ReActDecision(BaseModel):
    """One bounded ReAct clarification decision.

    ReAct does not choose another research tool in this design. After the planned
    evidence is collected, it decides whether information is still required from
    the engineer or whether the workflow can proceed to recommendation.
    """

    require_clarification: bool = False
    clarification_question: str = ""
    reason: str = ""


class EvidenceCitation(BaseModel):
    """A citation in the final answer; the quote must come from retrieved evidence."""

    source_id: str
    quote: str = Field(min_length=5, max_length=500)


class Recommendation(BaseModel):
    """Structured answer shown to the engineer."""

    # Taxonomy matches the organization's real triage categories (S1/S3 scenario
    # table), not a generically invented list - see data/triagescenarios.md and
    # the "ISSUE CATEGORY TAXONOMY" section of src/prompts/recommendation.py.
    possible_issue_category: Literal[
        "changes_not_reflecting",
        "deployment_halted",
        "health_check_failed",
        "invalid_configuration",
        "release_delay",
        "coordination_communication",
        "deployment_challenges_failure",
        "other",
    ] = "other"
    next_steps: list[str] = Field(default_factory=list)
    diagnostic_path: list[str] = Field(default_factory=list)
    source_traces: list[str] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    acceptable_alternatives: list[str] = Field(default_factory=list)
    should_not_repeat_the_below_action: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    clarification_questions_required: bool = False
    confidence: Literal["low", "medium", "high"] = "medium"


class Critique(BaseModel):
    """Critic output: PASS when the draft is acceptable, REVISE when material issues remain."""

    verdict: Literal["PASS", "REVISE"]
    issues: list[str] = Field(default_factory=list, max_length=8)
