# Fixes applied to this project

Six files were changed. The notebook itself (`notebooks/engineering_troubleshooting_copilot.ipynb`)
required no code changes — every bug was in the `src/` package or `requirements.txt`.
It's included here unmodified, alongside the fixed source files, so this zip is a
complete, ready-to-run copy.

A single-cell patch script (`apply_all_fixes.py`) is also included if you'd rather
patch your own already-running Colab copy than re-upload everything.

---

## 1. `src/mcp_client.py`

**Symptom:** `search_knowledge` / `search_web` MCP tool calls returned
`{'error': 'mcp_call_failed'}` with no further detail.

**Two real bugs, found in sequence:**

- **Missing `PYTHONPATH`.** The MCP server (`mcp_server.py`) runs as a separate
  Python subprocess. Python only puts the *script's own directory* on `sys.path`,
  not the project root, so `import config` and `from src.rag... import ...` failed
  inside that subprocess. Fixed by explicitly passing the project root via
  `PYTHONPATH` in the subprocess's environment.
- **`io.UnsupportedOperation: fileno`.** Colab/Jupyter replaces `sys.stderr` with
  a fake stream object that has no real OS file descriptor. `stdio_client()`
  defaults to using `sys.stderr` for the child process's stderr pipe, and
  `subprocess.Popen` needs a real file descriptor for that — so subprocess
  creation crashed immediately. Fixed by passing `errlog=sys.__stderr__` (the
  original, untouched stderr) instead of the ipykernel-patched `sys.stderr`.

## 2. `requirements.txt`

**Symptom:** once the two bugs above were fixed, the MCP server subprocess still
crashed on startup with:
```
ModuleNotFoundError: No module named 'mcp.server.fastmcp'. This is mcp 2.x,
where FastMCP was renamed to MCPServer...
```

**Root cause:** `requirements.txt` pinned `mcp[cli]>=2.0.0`, but the code
(`mcp_server.py`) is written against the `mcp` **1.x** API (`FastMCP`,
`@mcp.tool()`). Since `>=2.0.0` is satisfied by any current release, Colab
installed `mcp` 2.x and the import broke.

**Fix:** pinned to `mcp[cli]>=1.0.0,<2.0.0`.

## 3. `src/state.py`

**Symptom:** `InvalidUpdateError: At key 'evidence': Can receive only one value
per step` when the LangGraph planner selected more than one worker (e.g. both
`internal_knowledge` and `external_research`).

**Root cause:** the `evidence` field in `CopilotState` was declared as a plain
`list[dict]` with no reducer, making it a `LastValue` channel that only accepts
one write per superstep. But `specialist_worker()` runs in parallel via
`Send()`, and each worker writes to `evidence` in the same step. Every other
field written by parallel workers (`research_results`, `worker_roles_used`,
`mcp_events`, `react_observations`) already had `Annotated[..., operator.add]`
— `evidence` was simply missing it.

**Fix:** `evidence: list[dict]` → `evidence: Annotated[list[dict], operator.add]`.

## 4. `src/schemas.py`

**Symptom:** the deterministic evaluator (`evaluation/evaluator.py`) always
scored `category_accuracy: 0.0`, across every test case.

**Root cause:** `data/ground_truth.json` expects `possible_issue_category` to be
one of six fixed, snake_case labels (e.g. `"changes_not_reflecting"`), but the
`Recommendation` schema declared the field as a free `str`, so the model wrote
full descriptive sentences instead. The evaluator does an exact string
comparison, which can never match a sentence against a fixed label.

**Fix:** changed `possible_issue_category` from `str` to a closed `Literal` of
the same six taxonomy values used in `ground_truth.json` (plus `"other"` as a
safety fallback). Since `recommend()` uses structured output
(`invoke_structured(..., Recommendation, ...)`), this *forces* the model to
emit one of the exact expected values rather than just hinting at it.

## 5. `src/prompts/recommendation.py`

**Companion fix to #4.** Constraining the schema alone only fixes the *format*
of the output — it doesn't help the model pick the *correct* category. Added an
"ISSUE CATEGORY TAXONOMY" section to the prompt with a one-line definition of
each of the six categories, so the model can classify correctly, not just
validly.

## 6. `src/graph/workflow.py`

**Symptom:** the Gradio UI (`app.py`) crashed with
`TypeError: Object of type AgentSpec is not JSON serializable` as soon as the
planner produced a plan.

**Root cause:** the planner node stored raw `AgentSpec` **Pydantic model
instances** directly into `state["research_plan"]["selected_workers"]` instead
of plain dicts. That's fine for LangGraph's internal message passing and for
`print()`, but `app.py`'s `_ui_values()` calls `json.dumps()` on the state for
display, and Pydantic objects aren't JSON-serializable. This was also the
likely cause of the
`Deserializing unregistered type src.schemas.AgentSpec from checkpoint`
warning you saw earlier — LangGraph's SQLite checkpointer had to fall back to
pickling a raw class instance instead of storing plain, portable data.

**Fix:** `"selected_workers": safe_specs` →
`"selected_workers": [spec.model_dump() for spec in safe_specs]`. Confirmed
safe: `route_after_planner()` already reconstructs `AgentSpec` objects via
`AgentSpec.model_validate(item)`, which accepts plain dicts just as well as
live objects.

---

## After applying these fixes, in Colab

1. `!pip install -q "mcp[cli]>=1.0.0,<2.0.0"`
2. **Restart the Colab runtime** (`Runtime → Restart session`) — several of
   these fixes (schema changes, prompt changes) only take effect once cached
   Python modules are cleared, and a full restart is the most reliable way to
   guarantee that, especially for the long-running Gradio process.
3. Re-run: the pip install cell, the API key cell, `nest_asyncio.apply()`.
   You do **not** need to rebuild the Chroma index — it's already persisted to
   disk from your first run.
4. Continue from whichever cell you need (MCP test, LangGraph, evaluation, or
   Gradio).
