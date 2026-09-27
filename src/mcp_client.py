"""MCP client used by specialist workers.

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
import time
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import MAX_TOOL_RESULT_CHARS, MCP_TIMEOUT_SECONDS
from src.telemetry import log_event


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

    started = time.perf_counter()

    try:
        async with stdio_client(params, errlog=sys.__stderr__) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

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

                ok = not (isinstance(payload, dict) and payload.get("error"))
                log_event("mcp_call", {"tool": tool_name, "ok": ok, "latency_seconds": round(time.perf_counter() - started, 3)})
                return {
                    "tool": tool_name,
                    "ok": ok,
                    "data": payload,
                }
    except TimeoutError:
        log_event("mcp_call", {"tool": tool_name, "ok": False, "error": "tool_timeout", "latency_seconds": round(time.perf_counter() - started, 3)})
        return {"tool": tool_name, "ok": False, "data": {"error": "tool_timeout"}}
    except Exception:
        log_event("mcp_call", {"tool": tool_name, "ok": False, "error": "mcp_call_failed", "latency_seconds": round(time.perf_counter() - started, 3)})
        return {"tool": tool_name, "ok": False, "data": {"error": "mcp_call_failed"}}
