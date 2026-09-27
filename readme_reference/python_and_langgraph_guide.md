# Beginner Python + LangGraph guide

Use this document as a map. You do not need to understand Python syntax before understanding the responsibility of each method.

## The shared state

`src/state.py::CopilotState` is the shared folder travelling through LangGraph.

Important fields:

- `user_input`: the latest human submission.
- `turn_history`: all human submissions in this checkpointed thread.
- `context`: LLM1's structured understanding.
- `memory`: durable facts recalled from the engineer's memory store.
- `research_plan`: the Planner's selected workers and queries.
- `evidence`: internal and/or external research results.
- `react_decision`: whether engineer clarification is required before recommendation.
- `recommendation`: LLM3's structured answer.
- `critique`: critic result.
- `llm_usage`: application LLM token/latency records.

## `def`

`def memory_recall_node(state):` defines a Python function. LangGraph can register that function as a node.

## `async def` and `await`

`async def specialist_worker(...)` is used because the worker waits for MCP I/O.

`await call_mcp_tool(...)` means: wait for the tool response.

## Node

A node is one unit of work. Examples:

- `context_understanding_node()` -> LLM1.
- `memory_recall_node()` -> SQLite memory search.
- `planner_node()` -> Planner LLM.
- `specialist_worker()` -> dynamic internal/web worker.
- `react_controller_node()` -> ReAct LLM reasoning.
- `recommendation_agent_node()` -> LLM3.
- `critic_node()` -> critic LLM.
- `memory_write_node()` -> persistent memory write.

## Edge

`graph.add_edge("context_understanding", "memory_recall")` means the first node finishes and the next node is `memory_recall`.

## Conditional edge

`graph.add_conditional_edges(...)` means the current state decides what happens next.

Examples:

- planner -> specialist workers;
- specialist worker(s) -> ReAct;
- ReAct -> clarification OR recommendation;
- critic -> revision OR output guard.

## `Send()`

`Send("specialist_worker", payload)` dynamically creates a worker execution with its own small task payload. The number of workers is not hard-coded into the graph topology.

## `interrupt()`

`interrupt()` pauses the graph and asks the engineer for input. A checkpointer stores the state so the same `thread_id` can resume later.

When the engineer responds, the clarification node writes the response into `turn_history`, and the next node is **LLM1 again**.

## Memory vs RAG vs checkpoint

- Memory = stored engineer-specific facts.
- RAG = internal engineering knowledge retrieval.
- Checkpoint = saved LangGraph state for one thread.

## ReAct

ReAct means:

```text
Reason -> Action -> Observation -> Reason -> ...
```

In this implementation, the planned research has already run before ReAct. ReAct has a deliberately bounded decision:

```text
require_clarification = true
OR
require_clarification = false
```

When clarification is required, `interrupt()` pauses the checkpointed graph and the engineer response is sent back through LLM1, memory recall and the Planner before research runs again. When clarification is not required, the graph proceeds directly to Recommendation.

## Hybrid RAG

Internal search uses two retrieval methods:

```text
Chroma dense semantic search
+
BM25 keyword search
      |
      v
RRF
      |
      v
CrossEncoder reranker
```

## RRF

`src/rag/fusion.py::reciprocal_rank_fusion()` combines rankings using:

```text
1 / (k + rank)
```

Rank 1 contributes more points than rank 5. An item appearing high in several ranked lists receives points from each list.

## Evaluation

Think of evaluation as grading the copilot.

- deterministic metrics = explicit Python answer-key checks;
- LLM-as-a-judge = another LLM evaluates semantic quality;
- G-Eval = a specific customizable LLM-as-a-judge technique.

## Where to start reading code

1. `src/state.py`
2. `src/schemas.py`
3. `src/graph/workflow.py`
4. `src/agents.py`
5. `src/mcp_client.py` / `src/mcp_server.py`
6. `src/rag/`
7. `src/memory/store.py`
8. `evaluation/`
9. `app.py`
