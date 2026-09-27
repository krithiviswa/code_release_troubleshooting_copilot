"""Prompt used by the reflection critic."""
from src.skills.loader import load_skill


def critic_prompt(context: dict, recommendation: dict, evidence: list[dict], memory: list[dict]) -> str:
    """Build the critic prompt.

    NEXT: src/agents.py -> critique().
    """
    skill = load_skill("critic")
    return f"""
You are the independent Critic for an Engineering Troubleshooting recommendation.

SKILL:
{skill}

Return PASS when the draft is grounded, focused, actionable, correctly cited and avoids repeating completed actions.
Return REVISE when there is a material issue with correctness, evidence, citation, clarification or repetition.
Do not rewrite the recommendation; only identify material problems.

CONTEXT:
{context}

MEMORY:
{memory}

RECOMMENDATION:
{recommendation}

EVIDENCE:
{evidence}
"""
