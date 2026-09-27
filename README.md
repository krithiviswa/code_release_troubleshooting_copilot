# Engineering Troubleshooting Copilot — Final Reference Implementation

This is a synthetic AI engineering troubleshooting copilot designed as a learning/reference project for LangGraph, MCP, RAG, agents, memory and evaluation.

## What the system does

An engineer can paste:

- the current engineering problem;
- the current or recent troubleshooting conversation, including a long messy history over days/months;
- multiple related questions in one input.

The system:

1. uses **LLM1** to understand the complete human history;
2. recalls durable engineer-specific memory from prior interactions;
3. uses a **Planner** to choose internal knowledge, external web research, or both;
4. dynamically spawns only the required specialist workers with LangGraph `Send()`;
5. uses **Internal RAG** through MCP: Chroma dense retrieval + BM25 + multi-query + RRF + CrossEncoder;
6. uses an **External Research Worker** through MCP `search_web` only when fresh public/version-specific information is useful;
7. uses a bounded **ReAct** loop after research to decide whether additional information is required from the engineer;
8. uses **LLM3** to generate a structured recommendation;
9. uses a **Critic** and conditional revision;
10. performs a mechanical provenance check;
11. stores durable engineer facts in SQLite memory.

The system does not connect to production systems or execute operational changes. All supplied knowledge data is synthetic.

## Architecture

```text
Engineer
   |
Input Guard
   |
Context Understanding (LLM1)
   |
Memory Recall
   |
Planner / Orchestrator (LLM2)
   |
Send() dynamic specialist workers
   |
   +-------------------------+
   |                         |
Internal RAG            External Web Search
   |                         |
   +------------ Evidence ---+
                |
                v
       ReAct clarification gate
                |
        require clarification?
             /        \
           YES         NO
            |           |
       interrupt()      v
            |       Recommendation (LLM3)
        Engineer           |
        response          Critic
            |           /     \
            v         PASS    REVISE
     Context Understanding       |
            |                   LLM3
       Memory Recall             |
            |              Output Guard
         Planner                  |
            |              Memory Write
       RAG / Web                    |
            |                       |
           ReAct ----------------> END
```

Reference diagram: `readme_reference/interaction_diagram.png`

## Offline vs online

### Offline: run when the knowledge files change

```bash
python scripts/build_index.py
```

This executes:

```text
load_knowledge()
    -> split_markdown_records()
    -> chunk_records()
    -> get_embedder().encode()
    -> ChromaStore.add()
```

The resulting vector index is persisted in `chroma_db/`.

### Online: run the copilot

```bash
python app.py
```

Runtime executes:

```text
graph.ainvoke()
 -> validate_input_node()
 -> context_understanding_node()
 -> memory_recall_node()
 -> planner_node()
 -> Send() worker(s)
 -> react_controller_node()
 -> recommendation_agent_node()
 -> critic_node()
 -> output_guard_node()
 -> memory_write_node()
```

If ReAct determines clarification is needed:

```text
react_controller_node()
 -> interrupt()
 -> engineer responds
 -> context_understanding_node()  # LLM1 runs again
 -> memory_recall_node()
 -> planner_node()
 -> RAG / Web worker(s)
 -> react_controller_node()
```

The Planner does not ask for clarification. It chooses the internal RAG and/or external web research path. ReAct only decides whether missing current-case information must be obtained from the engineer before recommendation.

## RAG chunking strategy

The project intentionally does not use one generic splitter for every source.

### Runbook

- Markdown sections are separated into logical records during ingestion.
- A `RecursiveCharacterTextSplitter` is used inside each section.
- Preferred boundaries are paragraph -> line -> sentence -> word -> character.
- Overlap is configured.

### Continuous triage conversations

- The source is kept as one continuous logical conversation stream.
- Blank-line-separated speaker/message blocks are the natural boundary.
- Chunks accumulate whole message blocks up to the configured size.
- The last one or more whole message blocks can overlap into the next chunk.
- If one message is itself too long, the recursive splitter is used as a fallback.

### JIRA

- Top-level ticket headings create logical ticket records.
- Each ticket is then recursively chunked when needed.

## Metadata

The `.md` source files deliberately do not contain retrieval metadata headers.

Ingestion dynamically generates structural provenance metadata such as:

```text
source_type
document_name
record_index
record_title
source_id
parent_record_index
parent_source_id
chunk_index
```

Metadata is retained for traceability and citation. It is not used as a hard environment/application retrieval filter.

## Hybrid RAG and RRF

Internal RAG combines:

```text
query 1 ... query N
      |
      +--> Chroma dense retrieval
      |
      +--> BM25 keyword retrieval
                 |
                 +--> RRF
                       |
                       +--> CrossEncoder reranking
                              |
                              v
                           evidence
```

**RRF (Reciprocal Rank Fusion)** is a ranking-combination technique. It ignores the incompatible raw score scales of different retrievers and gives points based on rank using:

```text
1 / (RRF_K + rank)
```

The implementation lives in `src/rag/fusion.py::reciprocal_rank_fusion()`.

## Multi-query retrieval

LLM1 can create several retrieval query variants, and the engineer can also provide several questions in one input. Internal RAG runs each query, fuses their rankings, and then reranks the merged candidate pool.

## Memory vs RAG vs checkpointing

### Internal RAG

Searches organizational engineering knowledge:

```text
runbook
triage conversation history
JIRA
```

### Memory

Searches durable engineer-specific facts:

```text
"Paul from DevOps said ..."
"Engineer previously confirmed ..."
```

### Checkpointing

Stores the current LangGraph workflow state by `thread_id` so an interrupted conversation can resume later.

## Configuration

Edit `config.py` or set environment variables. Important knobs include:

```text
MODEL_PROFILE
CONTEXT_MODEL
PLANNER_MODEL
RECOMMENDATION_MODEL
CRITIC_MODEL
EVAL_JUDGE_MODEL

CHUNK_MAX_CHARS
CHUNK_MIN_CHARS
CHUNK_OVERLAP_CHARS
CONVERSATION_OVERLAP_BLOCKS

DENSE_CANDIDATE_K
BM25_CANDIDATE_K
FINAL_K
RRF_K
MAX_RETRIEVAL_QUERIES

MAX_REACT_STEPS
MAX_DYNAMIC_WORKERS
MAX_CLARIFICATIONS
MAX_MCP_CALLS
MAX_REFLECTION_ROUNDS
```

Start with:

```text
MODEL_PROFILE=light
```

and move to:

```text
MODEL_PROFILE=advanced
```

when you are ready. Free/trial model access is account-dependent; the application simply lets you switch profiles without changing agent code.

## Google Colab

1. Open `notebooks/engineering_troubleshooting_copilot.ipynb` from GitHub or upload the notebook.
2. Install requirements.
3. Set `OPENAI_API_KEY`.
4. Run `scripts/build_index.py` once.
5. Run the local RAG check.
6. Run the MCP internal search check.
7. Run an end-to-end LangGraph example.
8. Run a clarification/resume example.
9. Run the deterministic benchmark.
10. Optionally run DeepEval/G-Eval.
11. Launch Gradio.

Example clone setup:

```python
!git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
%cd YOUR_REPO
!pip install -r requirements.txt
```

Or upload the ZIP and unzip it in Colab.

## Gradio

```bash
python app.py
```

In Colab:

```python
from app import launch_app
launch_app(share=True)
```

The UI supports:

- one free-form input for a current issue or long messy history;
- persistent engineer ID;
- checkpointed thread ID;
- clarification response and resume;
- recommendation/evidence/context display;
- planner/ReAct/telemetry display;
- evaluation tab.

## Evaluation

Two layers are used.

### Deterministic

These are transparent Python rules:

- worker selection accuracy
- worker execution success
- category accuracy
- next-action coverage
- source/citation coverage
- no-repeat rate
- clarification accuracy (whether ReAct actually interrupted when required)
- memory match
- retrieval source hit/recall/MRR
- case pass rate

### LLM-as-a-judge

DeepEval provides:

- Answer Relevancy
- Faithfulness
- Contextual Relevancy
- Contextual Precision
- Contextual Recall
- G-Eval: `Next Action Quality`

G-Eval is a specific LLM-as-a-judge method that uses a natural-language criterion/rubric to evaluate a result. It is not a replacement for deterministic checks.

### Operational telemetry

The project captures:

- wall-clock latency
- LLM call count
- input/output/total tokens
- MCP call count
- worker roles used
- ReAct steps
- clarification turns
- memory hits
- revisions
- evidence count

## Beginner code map

Start in this order:

1. `src/state.py` — what travels through LangGraph?
2. `src/schemas.py` — what shape does each important LLM result have?
3. `src/graph/workflow.py` — which node runs next?
4. `src/agents.py` — where are the LLM calls?
5. `src/mcp_client.py` / `src/mcp_server.py` — how does a worker call a tool?
6. `src/rag/` — how are internal sources retrieved?
7. `src/memory/store.py` — how are durable facts remembered?
8. `evaluation/` — how do we prove the system is working?
9. `app.py` — how does the UI start/resume the graph?

Each important method contains a teaching docstring/comments for:

```text
PURPOSE
READS
CALLS
WRITES
NEXT: filename.method()
```

## Install / test

```bash
pip install -r requirements.txt
pytest -q
```

DeepEval calls are optional because they invoke the judge model and therefore add cost/latency.
