# Evaluation guide

## Why two evaluation layers?

### Deterministic metrics

These are ordinary Python calculations with explicit rules. They are like an answer-key checker.

Examples:

- Did the expected source appear?
- Did the planner select the expected worker set?
- Did the answer cover enough expected actions?
- Did the answer repeat a completed action?
- Did ReAct actually interrupt for clarification when the case required engineer-specific information?

They are transparent and repeatable.

### LLM-as-a-judge metrics

These ask another LLM to judge semantic quality. They are useful when two answers use different words but mean the same thing.

DeepEval currently documents these as LLM-as-a-judge metrics, including Answer Relevancy, Faithfulness, Contextual Relevancy, Contextual Precision and Contextual Recall. urlDeepEval metric overviewhttps://deepeval.com/docs/metrics-introduction

## G-Eval

G-Eval is a specific LLM-as-a-judge technique for custom criteria. In this project the custom criterion is **Next Action Quality**. The rubric tells the judge what good looks like: useful next action, evidence support, correct clarification behavior and no repetition of completed actions. urlDeepEval G-Eval documentationhttps://deepeval.com/docs/metrics-llm-evals

## Deterministic metrics in this project

| Metric | Plain English |
|---|---|
| Worker selection accuracy | Did the planner invoke exactly the expected internal/external worker set? |
| Worker execution success | Did the expected worker actually return a usable result? |
| Category accuracy | Did the model identify the expected issue category? |
| Next-action coverage | How many expected actions were represented in the response? |
| Source/citation coverage | How many expected evidence sources were cited? |
| No-repeat rate | Did the response avoid repeating actions the engineer already completed? |
| Clarification accuracy | Did the graph actually perform the expected ReAct clarification interrupt? |
| Memory match | Did recalled memory contain the expected remembered fact? |
| Retrieval source hit | Did any expected source appear in the retrieved ranking? |
| Retrieval source recall | What fraction of expected sources were retrieved? |
| Retrieval MRR | How early was the first expected source in the ranking? |
| Case pass rate | What fraction of cases satisfy the core deterministic contract? |

## Operational metrics

The benchmark also captures:

- end-to-end wall-clock latency
- number of application LLM calls
- input/output/total tokens from application LLM calls
- MCP calls
- workers used
- ReAct steps
- clarification turns
- memory hits
- revisions
- evidence count

## Important interpretation

A high deterministic score does not prove the answer is semantically excellent. A high LLM-judge score does not prove every objective requirement was met. Use both layers together.
