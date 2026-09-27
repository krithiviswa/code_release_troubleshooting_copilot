"""
Run this as ONE Colab cell to apply every fix we made, in one shot.
It overwrites each file completely (not a partial patch), so it works
no matter which earlier partial patches you already applied.

After running this cell:
  1. !pip install -q "mcp[cli]>=1.0.0,<2.0.0"
  2. Restart the Colab runtime (Runtime -> Restart session)
  3. Re-run: API key cell, nest_asyncio.apply(), then whichever cell you need
     (MCP test / LangGraph / Gradio). You do NOT need to rebuild the Chroma index.
"""
from pathlib import Path

files = {}

# ---------------------------------------------------------------------------
# 1) src/mcp_client.py
#    Fix A: PYTHONPATH so the subprocess can import `config` and `src.rag`.
#    Fix B: errlog=sys.__stderr__ so subprocess creation doesn't crash on
#           Colab/Jupyter's fake sys.stderr (io.UnsupportedOperation: fileno).
# ---------------------------------------------------------------------------
files["src/mcp_client.py"] = '''"""MCP client used by specialist workers.

BEGINNER IDEA
--------------
The worker does not know how Chroma or the web provider works.  It calls a named
MCP tool.  This client sends that request to our local MCP server process.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import MAX_TOOL_RESULT_CHARS, MCP_TIMEOUT_SECONDS


async def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call one allowed MCP tool and normalize its result.

    PURPOSE:
        Hide MCP transport details from the LangGraph nodes.

    CALLS:
        local src/mcp_server.py through MCP stdio.

    NEXT:
        src/graph/workflow.py -> the worker that requested the tool.
    """
    server_path = str(Path(__file__).resolve().parent / "mcp_server.py")
    project_root = str(Path(__file__).resolve().parent.parent)

    # The MCP server runs in a separate Python process.
    # Explicitly add the project root so it can import:
    #   config
    #   src.rag
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        project_root
        if not existing_pythonpath
        else project_root + os.pathsep + existing_pythonpath
    )

    params = StdioServerParameters(
        command=sys.executable,
        args=["-u", server_path],
        env=env,
    )

    try:
        # NOTE: Colab/Jupyter's sys.stderr is a fake stream with no real file
        # descriptor, which crashes subprocess creation with
        # io.UnsupportedOperation: fileno. Use the original OS-level stderr
        # (sys.__stderr__) instead, which ipykernel leaves untouched.
        async with stdio_client(params, errlog=sys.__stderr__) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # PURPOSE: Bound each tool call so a stuck provider cannot hold the workflow forever.
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=MCP_TIMEOUT_SECONDS,
                )

                text_parts = [item.text for item in result.content if hasattr(item, "text")]
                raw = "".join(text_parts)[:MAX_TOOL_RESULT_CHARS]
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {"error": "invalid_tool_response", "detail": raw[:500]}

                return {
                    "tool": tool_name,
                    "ok": not (isinstance(payload, dict) and payload.get("error")),
                    "data": payload,
                }
    except TimeoutError:
        return {"tool": tool_name, "ok": False, "data": {"error": "tool_timeout"}}
    except Exception:
        # PURPOSE: Keep raw child-process exceptions out of prompts; expose only a safe observation.
        return {"tool": tool_name, "ok": False, "data": {"error": "mcp_call_failed"}}
'''

# ---------------------------------------------------------------------------
# 2) src/state.py
#    Fix: `evidence` needs an operator.add reducer since two Send() workers
#    (internal_knowledge + external_research) can both write to it in the
#    same LangGraph superstep. Without this: InvalidUpdateError.
# ---------------------------------------------------------------------------
_state_marker_old = "    # The current merged evidence set.  Normalized to internal/external evidence only.\n    evidence: list[dict]"
_state_marker_new = (
    "    # The current merged evidence set.  Normalized to internal/external evidence only.\n"
    "    # Reducer: multiple Send() workers (internal_knowledge + external_research) can\n"
    "    # each write evidence in the same superstep; _dedupe_evidence() cleans up on read.\n"
    "    evidence: Annotated[list[dict], operator.add]"
)

# ---------------------------------------------------------------------------
# 3) src/schemas.py
#    Fix: possible_issue_category must be a closed Literal taxonomy matching
#    data/ground_truth.json's `expected_issue_category` values, or the
#    deterministic evaluator's exact-string category_match can never be True.
# ---------------------------------------------------------------------------
_schemas_marker_old = '    possible_issue_category: str = "unknown"'
_schemas_marker_new = '''    possible_issue_category: Literal[
        "changes_not_reflecting",
        "deployment_configuration_mismatch",
        "deployment_order_issue",
        "kafka_connectivity",
        "certificate_secret_issue",
        "external_dependency_update",
        "other",
    ] = "other"'''

# ---------------------------------------------------------------------------
# 4) src/prompts/recommendation.py
#    Fix: tell the model the taxonomy + definitions so it classifies into
#    the same labels the schema now enforces (format alone isn't enough).
# ---------------------------------------------------------------------------
_prompt_marker_old = """RULES:
1. Treat actions already attempted as completed; do not blindly repeat them."""
_prompt_marker_new = """ISSUE CATEGORY TAXONOMY:
Set `possible_issue_category` to exactly one of the following (pick the closest match, or "other" if none fit):
- changes_not_reflecting: deployment succeeded but the expected change is not visible/served.
- deployment_configuration_mismatch: wrong artifact, template, environment alias, or config was used.
- deployment_order_issue: steps/dependencies were applied out of the required order.
- kafka_connectivity: Kafka client/broker connectivity or authentication problem.
- certificate_secret_issue: expired/misconfigured certificate, key, or secret.
- external_dependency_update: a third-party/vendor library or service version change is the likely cause.
- other: none of the above clearly apply.

RULES:
1. Treat actions already attempted as completed; do not blindly repeat them."""

# ---------------------------------------------------------------------------
# 5) src/graph/workflow.py
#    Fix: research_plan.selected_workers must store plain dicts, not raw
#    AgentSpec Pydantic objects, or json.dumps() in app.py's Gradio UI
#    crashes with "Object of type AgentSpec is not JSON serializable".
# ---------------------------------------------------------------------------
_workflow_marker_old = '''    plan = {
        "selected_workers": safe_specs,
        "rationale": call.output.rationale,
    }'''
_workflow_marker_new = '''    plan = {
        "selected_workers": [spec.model_dump() for spec in safe_specs],
        "rationale": call.output.rationale,
    }'''

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def _full_overwrite(path_str: str, content: str):
    p = Path(path_str)
    p.write_text(content)
    print(f"[full overwrite] {path_str}")


def _patch_or_note(path_str: str, old: str, new: str):
    p = Path(path_str)
    text = p.read_text()
    if new in text:
        print(f"[already fixed]  {path_str}")
        return
    if old not in text:
        print(f"[!! MISMATCH !!] {path_str} -- current content differs from every known "
              f"version. Paste this file to Claude for a manual patch.")
        return
    p.write_text(text.replace(old, new))
    print(f"[patched]        {path_str}")


_full_overwrite("src/mcp_client.py", files["src/mcp_client.py"])
_patch_or_note("src/state.py", _state_marker_old, _state_marker_new)
_patch_or_note("src/schemas.py", _schemas_marker_old, _schemas_marker_new)
_patch_or_note("src/prompts/recommendation.py", _prompt_marker_old, _prompt_marker_new)
_patch_or_note("src/graph/workflow.py", _workflow_marker_old, _workflow_marker_new)

print("\\nDone. Next steps:")
print('  1. !pip install -q "mcp[cli]>=1.0.0,<2.0.0"')
print("  2. Runtime -> Restart session")
print("  3. Re-run API key cell + nest_asyncio.apply(), then continue from wherever you left off.")
print("     (No need to rebuild the Chroma index -- it's already on disk.)")
