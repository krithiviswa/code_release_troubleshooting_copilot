# Reference patterns used in this capstone

| Pattern | Where | Why it exists |
|---|---|---|
| Modular RAG | `src/rag/` | Retrieval stages can be changed independently. |
| Document-aware chunking | `src/rag/chunking.py` | Different source shapes need different natural boundaries. |
| Hybrid retrieval | Chroma + BM25 + RRF | Semantic search and exact technical terms complement each other. |
| Multi-query retrieval | `QueryContext.retrieval_queries` | Several search perspectives reduce dependence on one query wording. |
| CrossEncoder reranking | `src/rag/reranking.py` | Re-score the final candidate pool with query+document relevance. |
| Structured LLM output | Pydantic schemas | Downstream Python receives predictable fields. |
| Dynamic workers | LangGraph `Send()` | Planner can choose internal, external or both at runtime. |
| ReAct clarification gate | `react_controller_node()` | Reason over the planned evidence and decide whether engineer clarification is required. |
| Clarification interrupt | `interrupt()` + checkpoint | ReAct can pause the graph when current-case information is missing; the response is then fed back to LLM1. |
| Persistent memory | SQLite FTS5 | Durable engineer-specific facts survive across threads. |
| Checkpointing | Async SQLite saver | Conversation state can resume by `thread_id`. |
| Skills | `skills/*/SKILL.md` | Reusable role-specific operating instructions. |
| Reflection | Critic + recommendation revision | A second model pass catches material problems. |
| Deterministic eval | `evaluation/metrics.py` | Transparent, repeatable regression checks. |
| LLM-as-a-judge | DeepEval | Semantic quality is hard to measure with exact rules alone. |
| G-Eval | `Next Action Quality` | Custom domain rubric judged by an LLM. |
| Token telemetry | `src/llm.py` | Compare model profiles and workflow cost. |
| Guardrails | input/output | Bound input and verify provenance. |
