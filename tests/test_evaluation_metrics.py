from evaluation.metrics import best_action_coverage, retrieval_source_metrics, similar, worker_selection_accuracy


def test_stopwords_do_not_dominate_match():
    # "the" and "is" are ignored because they carry little technical meaning here.
    assert similar("the JVM is restarted", "JVM restart") >= 0.45


def test_action_coverage():
    coverage, matches = best_action_coverage(
        ["Verify JVM restart requirement", "Verify deployed artifact/version"],
        ["Confirm whether the JVM restart was completed", "Check the deployed build version"],
    )
    assert coverage == 1.0
    assert len(matches) == 2


def test_retrieval_source_metrics_support_generated_chunk_prefixes():
    evidence = [
        {"metadata": {"source_id": "runbook::changes-not-reflecting-after-deployment::chunk-0002"}},
        {"metadata": {"source_id": "jira::rel-10245-payment-release::chunk-0001"}},
    ]
    metrics = retrieval_source_metrics(
        ["runbook::changes-not-reflecting-after-deployment::", "jira::rel-10245-payment-release::"],
        evidence,
    )
    assert metrics["retrieval_source_hit"] is True
    assert metrics["retrieval_source_recall"] == 1.0
    assert metrics["retrieval_source_mrr"] == 1.0


def test_worker_selection_modes():
    assert worker_selection_accuracy("internal_only", ["internal_knowledge"])
    assert worker_selection_accuracy("external_only", ["external_research"])
    assert worker_selection_accuracy("both", ["internal_knowledge", "external_research"])
