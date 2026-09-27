"""DeepEval LLM-as-a-judge and G-Eval metrics.

BEGINNER IDEA
--------------
Deterministic evaluation asks objective yes/no questions.  LLM-as-a-judge lets
another LLM read the request, evidence and answer and judge semantic quality.
"""
from __future__ import annotations

import json

from config import EVAL_JUDGE_MODEL, EVAL_JUDGE_THRESHOLD, EVAL_LLM_METRIC_LIMIT


def _expected_output(case: dict) -> str:
    """Turn one ground-truth case into a compact ideal-output reference."""
    return json.dumps(
        {
            "expected_issue_category": case.get("expected_issue_category"),
            "expected_next_actions": case.get("expected_next_actions", []),
            "acceptable_alternative_actions": case.get("acceptable_alternative_actions", []),
            "actions_that_should_NOT_be_repeated": case.get("actions_that_should_NOT_be_repeated", []),
            "clarification_required": case.get("clarification_required", False),
            "expected_clarification_questions": case.get("expected_clarification_questions", []),
            "expected_supporting_evidence": case.get("expected_supporting_evidence", []),
        },
        indent=2,
    )


def judge_case(case: dict, prediction: dict, evidence: list[dict]) -> dict:
    """Run configured DeepEval metrics for one benchmark case.

    NEXT: evaluation/evaluator.py -> row.update().
    """
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
        GEval,
    )
    from deepeval.test_case import LLMTestCase, SingleTurnParams

    actual_output = json.dumps(prediction, indent=2, ensure_ascii=False)
    retrieval_context = [item.get("content", "") for item in evidence]
    test_case = LLMTestCase(
        input=case.get("current_problem", ""),
        actual_output=actual_output,
        expected_output=_expected_output(case),
        retrieval_context=retrieval_context,
    )

    # METRIC PURPOSE: Is the final answer relevant to the engineer's problem?
    answer_relevancy = AnswerRelevancyMetric(
        model=EVAL_JUDGE_MODEL,
        threshold=EVAL_JUDGE_THRESHOLD,
        include_reason=True,
    )

    # METRIC PURPOSE: Are answer claims supported by the retrieved evidence?
    faithfulness = FaithfulnessMetric(
        model=EVAL_JUDGE_MODEL,
        threshold=EVAL_JUDGE_THRESHOLD,
        include_reason=True,
    )

    # METRIC PURPOSE: Is the retrieved context mostly relevant rather than noisy?
    contextual_relevancy = ContextualRelevancyMetric(
        model=EVAL_JUDGE_MODEL,
        threshold=EVAL_JUDGE_THRESHOLD,
        include_reason=True,
    )

    # METRIC PURPOSE: Did the retriever/reranker put useful chunks ahead of irrelevant ones?
    contextual_precision = ContextualPrecisionMetric(
        model=EVAL_JUDGE_MODEL,
        threshold=EVAL_JUDGE_THRESHOLD,
        include_reason=True,
    )

    # METRIC PURPOSE: Did retrieval capture enough information to support the expected result?
    contextual_recall = ContextualRecallMetric(
        model=EVAL_JUDGE_MODEL,
        threshold=EVAL_JUDGE_THRESHOLD,
        include_reason=True,
    )

    # METRIC PURPOSE: Domain-specific judgement of troubleshooting usefulness.
    # The criteria are the rubric: they tell the judge what "good" means for this project.
    next_action_quality = GEval(
        name="Next Action Quality",
        criteria=(
            "Judge whether the actual troubleshooting recommendation is actionable and appropriate for the input. "
            "Use the expected output as the reference. Reward correct expected actions or supported acceptable alternatives, "
            "appropriate clarification behavior, grounding in retrieval context, and avoidance of already-attempted actions. "
            "Penalize unsupported claims, repeated actions, and unnecessary questions."
        ),
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
            SingleTurnParams.RETRIEVAL_CONTEXT,
        ],
        threshold=EVAL_JUDGE_THRESHOLD,
    )

    all_metrics = [
        ("answer_relevancy", answer_relevancy),
        ("faithfulness", faithfulness),
        ("contextual_relevancy", contextual_relevancy),
        ("contextual_precision", contextual_precision),
        ("contextual_recall", contextual_recall),
        ("next_action_quality", next_action_quality),
    ]
    selected = all_metrics[: max(1, min(EVAL_LLM_METRIC_LIMIT, len(all_metrics)))]

    result = {
        "judge_model": EVAL_JUDGE_MODEL,
        "metrics_run": [name for name, _ in selected],
    }

    for name, metric in selected:
        # Each measure() call asks the configured judge model to score this case.
        metric.measure(test_case)
        result[f"{name}_score"] = round(float(metric.score), 3)
        result[f"{name}_reason"] = metric.reason

    return result
