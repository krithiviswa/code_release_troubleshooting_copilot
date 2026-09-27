"""Deterministic evaluation metrics for repeatable regression checks.

BEGINNER IDEA
--------------
These metrics are like an answer-key checker.  Python applies explicit rules to
compare the copilot's behavior with the ground truth.  They complement the
LLM-as-a-judge metrics in evaluation/llm_judge.py.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from statistics import mean

from config import (
    EVAL_ACTION_SIMILARITY_THRESHOLD,
    EVAL_CASE_ACTION_COVERAGE_THRESHOLD,
    EVAL_CASE_SOURCE_COVERAGE_THRESHOLD,
    EVAL_REPEAT_SIMILARITY_THRESHOLD,
    EVAL_STOPWORDS,
)


def _tokens(text: str) -> set[str]:
    """Return technical-ish words used by our transparent similarity check.

    WHY: Common words such as "the" and "and" do not tell us whether two
    troubleshooting actions are similar.  Removing them makes the regression
    check a little more useful.
    """
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {word for word in words if word not in EVAL_STOPWORDS}


def similar(expected: str, actual: str) -> float:
    """Measure simple text similarity for deterministic regression checks.

    IMPORTANT: This is NOT semantic LLM evaluation.  It is deliberately simple
    and reproducible.  DeepEval/G-Eval performs the semantic judgement separately.
    """
    exp = _tokens(expected)
    got = _tokens(actual)
    overlap = len(exp & got) / max(1, len(exp))
    sequence = SequenceMatcher(None, expected.lower().strip(), actual.lower().strip()).ratio()
    return max(overlap, sequence)


def best_action_coverage(expected: list[str], actual: list[str]) -> tuple[float, list[tuple[str, str, float]]]:
    """METRIC: Next-action coverage.

    SIMPLE PURPOSE: What fraction of the expected troubleshooting actions did
    the model mention in a sufficiently similar form?

    SCORE: 1.0 means every expected action had a matching model action.

    NEXT: evaluate_case().
    """
    if not expected:
        return 1.0, []

    matched: list[tuple[str, str, float]] = []
    for expected_action in expected:
        candidates = [(similar(expected_action, actual_action), actual_action) for actual_action in actual]
        best_score, best_text = max(candidates, default=(0.0, ""))
        if best_score >= EVAL_ACTION_SIMILARITY_THRESHOLD:
            matched.append((expected_action, best_text, round(best_score, 2)))
    return len(matched) / len(expected), matched


def _expected_source_matches(expected: str, actual: str) -> bool:
    """Allow ground truth to name a source family/prefix because chunk IDs are generated dynamically.

    Example:
        expected = "runbook::changes-not-reflecting-after-deployment::"
        actual   = "runbook::changes-not-reflecting-after-deployment::chunk-0002"
    """
    if expected.endswith("::") or expected.endswith("*"):
        prefix = expected.rstrip("*")
        return actual.lower().startswith(prefix.lower())
    return actual.lower() == expected.lower()


def source_coverage(expected: list[str], actual: list[str]) -> float:
    """METRIC: Citation/source coverage.

    SIMPLE PURPOSE: How many expected evidence sources were actually cited by the answer?

    NEXT: evaluate_case().
    """
    if not expected:
        return 1.0
    matched = sum(1 for wanted in expected if any(_expected_source_matches(wanted, got) for got in actual))
    return matched / len(expected)


def repeat_violation(blocked_actions: list[str], actual: list[str]) -> bool:
    """METRIC: No-repeat check.

    SIMPLE PURPOSE: Did the final recommendation repeat something the engineer
    had already completed?

    NEXT: evaluate_case().
    """
    for blocked in blocked_actions:
        if any(similar(blocked, candidate) >= EVAL_REPEAT_SIMILARITY_THRESHOLD for candidate in actual):
            return True
    return False


def retrieval_source_metrics(expected_sources: list[str], evidence: list[dict]) -> dict:
    """METRICS: source hit, source recall and MRR for the retrieved evidence.

    - Source hit: did at least one expected source appear?
    - Source recall: what fraction of expected sources appeared?
    - MRR: how high was the first expected source in the ranked evidence?

    NEXT: evaluate_case().
    """
    actual_ids: list[str] = []
    for item in evidence:
        metadata = item.get("metadata", {})
        actual_ids.append(str(metadata.get("source_id") or item.get("id") or ""))

    if not expected_sources:
        return {"retrieval_source_hit": True, "retrieval_source_recall": 1.0, "retrieval_source_mrr": 1.0}

    positions: list[int] = []
    for expected in expected_sources:
        matching_positions = [index + 1 for index, actual in enumerate(actual_ids) if _expected_source_matches(expected, actual)]
        if matching_positions:
            positions.append(min(matching_positions))

    return {
        "retrieval_source_hit": bool(positions),
        "retrieval_source_recall": len(positions) / len(expected_sources),
        "retrieval_source_mrr": 1.0 / min(positions) if positions else 0.0,
    }


def worker_selection_accuracy(expected_mode: str, actual_roles: list[str]) -> bool:
    """METRIC: Did the Planner/graph invoke the expected worker set?

    SIMPLE PURPOSE: Validate dynamic routing itself, not just the final answer.
    """
    expected_sets = {
        "internal_only": {"internal_knowledge"},
        "external_only": {"external_research"},
        "both": {"internal_knowledge", "external_research"},
        "none": set(),
    }
    return set(actual_roles) == expected_sets.get(expected_mode, set())


def memory_match(expected_fragments: list[str], memory: list[dict]) -> bool:
    """METRIC: Did the memory search return the expected remembered fact fragments?"""
    if not expected_fragments:
        return True
    combined = " ".join(str(item.get("fact", "")) for item in memory).lower()
    return all(fragment.lower() in combined for fragment in expected_fragments)


def evaluate_case(case: dict, prediction: dict, evidence: list[dict], state: dict) -> dict:
    """Run all objective checks for one benchmark case.

    NEXT: evaluation/evaluator.py -> summarize().
    """
    actual_actions = prediction.get("next_steps", []) + prediction.get("diagnostic_path", [])
    action_coverage, matches = best_action_coverage(case.get("expected_next_actions", []), actual_actions)

    cited_sources = prediction.get("source_traces", [])
    source_cov = source_coverage(case.get("expected_supporting_evidence", []), cited_sources)

    category_match = (
        str(prediction.get("possible_issue_category", "")).strip().lower()
        == str(case.get("expected_issue_category", "")).strip().lower()
    )

    actual_clarification = int(state.get("clarification_count", 0)) > 0
    clarification_match = actual_clarification == bool(case.get("clarification_required", False))

    repeated = repeat_violation(case.get("actions_that_should_NOT_be_repeated", []), actual_actions)

    retrieval = retrieval_source_metrics(case.get("expected_supporting_evidence", []), evidence)
    actual_roles = sorted(set(state.get("worker_roles_used", [])))
    worker_selection = worker_selection_accuracy(case.get("expected_research_mode", "none"), actual_roles)

    expected_worker_roles = {
        "internal_only": {"internal_knowledge"},
        "external_only": {"external_research"},
        "both": {"internal_knowledge", "external_research"},
        "none": set(),
    }.get(case.get("expected_research_mode", "none"), set())

    successful_roles = {
        event.get("role")
        for event in state.get("mcp_events", [])
        if event.get("ok")
    }
    worker_execution_success = expected_worker_roles.issubset(successful_roles)

    memory_ok = memory_match(case.get("expected_memory_contains", []), state.get("memory", []))

    # Core deterministic pass rule.  For source-free external-only cases, source coverage is 1 by definition.
    case_pass = (
        category_match
        and action_coverage >= EVAL_CASE_ACTION_COVERAGE_THRESHOLD
        and source_cov >= EVAL_CASE_SOURCE_COVERAGE_THRESHOLD
        and clarification_match
        and not repeated
        and worker_selection
        and worker_execution_success
        and memory_ok
    )

    return {
        "test_id": case["test_id"],
        "category_match": category_match,
        "next_action_coverage": round(action_coverage, 3),
        "matched_actions": len(matches),
        "expected_actions": len(case.get("expected_next_actions", [])),
        "source_coverage": round(source_cov, 3),
        "no_repeat_pass": not repeated,
        "clarification_match": clarification_match,
        "worker_selection_accuracy": worker_selection,
        "worker_execution_success": worker_execution_success,
        "memory_match": memory_ok,
        "actual_worker_roles": actual_roles,
        "case_pass": case_pass,
        **{
            key: round(value, 3) if isinstance(value, float) else value
            for key, value in retrieval.items()
        },
    }


def summarize(rows: list[dict]) -> dict:
    """Aggregate deterministic metrics across the benchmark.

    SIMPLE PURPOSE: Turn many per-case results into one dashboard-like summary.
    """
    def avg(key: str) -> float:
        return round(mean([float(row[key]) for row in rows]), 3) if rows else 0.0

    return {
        "cases_run": len(rows),
        "category_accuracy": avg("category_match"),
        "avg_next_action_coverage": avg("next_action_coverage"),
        "avg_source_coverage": avg("source_coverage"),
        "no_repeat_rate": avg("no_repeat_pass"),
        "clarification_accuracy": avg("clarification_match"),
        "worker_selection_accuracy": avg("worker_selection_accuracy"),
        "worker_execution_success": avg("worker_execution_success"),
        "memory_match_rate": avg("memory_match"),
        "case_pass_rate": avg("case_pass"),
        "retrieval_source_hit_rate": avg("retrieval_source_hit"),
        "retrieval_source_recall": avg("retrieval_source_recall"),
        "retrieval_source_mrr": avg("retrieval_source_mrr"),
    }
