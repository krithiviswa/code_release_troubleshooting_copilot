"""Local MCP server exposing exactly two controlled capabilities.

1. search_knowledge -> internal RAG
2. search_web -> public web research

No production or enterprise diagnostic APIs are exposed.
"""
from __future__ import annotations

import json
from pathlib import Path


from mcp.server.fastmcp import FastMCP

from config import MAX_TOOL_RESULT_CHARS, MAX_WEB_RESULT_CHARS, MAX_WEB_RESULTS, MOCK_WEB_SEARCH, TAVILY_API_KEY
from src.rag.pipeline import get_runtime_rag

mcp = FastMCP("engineering-troubleshooting-copilot")


def _bounded_json(payload) -> str:
    """Serialize a tool result without returning invalid/truncated JSON.

    NEXT: the MCP client receives the returned string and parses it.
    """
    text = json.dumps(payload, ensure_ascii=False)
    if len(text) <= MAX_TOOL_RESULT_CHARS:
        return text

    if isinstance(payload, list):
        trimmed = list(payload)
        while trimmed and len(json.dumps(trimmed, ensure_ascii=False)) > MAX_TOOL_RESULT_CHARS:
            trimmed.pop()
        return json.dumps(trimmed, ensure_ascii=False)

    return json.dumps({"error": "tool_result_too_large"})


@mcp.tool()
def search_knowledge(query: str = "", queries: list[str] | None = None, top_k: int = 8) -> str:
    """Search internal engineering knowledge through the persisted hybrid RAG pipeline.

    NEXT: src/rag/pipeline.py -> HybridRAG.retrieve_and_rerank_many().
    """
    try:
        rag = get_runtime_rag()
        # PURPOSE: Accept several query variants so the RAG pipeline can perform multi-query fusion.
        clean_queries = queries or ([query] if query.strip() else [])
        results = rag.retrieve_and_rerank_many(clean_queries, final_k=top_k)
        return _bounded_json(results)
    except Exception:
        return _bounded_json({"error": "knowledge_search_failed"})


@mcp.tool()
def search_web(query: str, max_results: int = MAX_WEB_RESULTS) -> str:
    """Search current public web information through Tavily when configured.

    PURPOSE:
        Support version-specific/vendor/current public information that is not expected
        to exist in the synthetic internal knowledge base.

    NEXT: external research worker receives these URLs/content as external evidence.
    """
    # PURPOSE: Evaluation can use deterministic synthetic public observations.
    # Normal application runs keep MOCK_WEB_SEARCH=false and use the real public web provider.
    if MOCK_WEB_SEARCH:
        mock_path = Path(__file__).resolve().parent.parent / "data" / "mock_web.json"
        try:
            mock_rows = json.loads(mock_path.read_text(encoding="utf-8"))
            tokens = set(query.lower().split())
            ranked = []
            for row in mock_rows:
                overlap = sum(1 for tag in row.get("query_tags", []) if tag.lower() in tokens)
                if overlap:
                    ranked.append((overlap, row))
            ranked.sort(key=lambda pair: pair[0], reverse=True)
            return _bounded_json([
                {
                    "title": row.get("title", ""),
                    "url": row.get("url", ""),
                    "content": row.get("content", "")[:MAX_WEB_RESULT_CHARS],
                    "score": float(score),
                }
                for score, row in ranked[:MAX_WEB_RESULTS]
            ])
        except Exception:
            return _bounded_json({"error": "mock_web_search_failed"})

    if not TAVILY_API_KEY:
        return _bounded_json(
            {
                "error": "web_search_not_configured",
                "detail": "Set TAVILY_API_KEY to enable public web search.",
            }
        )

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=query,
            max_results=min(max(int(max_results), 1), MAX_WEB_RESULTS),
        )
        results = []
        for item in response.get("results", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": str(item.get("content", ""))[:MAX_WEB_RESULT_CHARS],
                    "score": item.get("score"),
                }
            )
        return _bounded_json(results)
    except Exception:
        return _bounded_json({"error": "web_search_failed"})


if __name__ == "__main__":
    # PURPOSE: Launch the stdio MCP server when the client starts this file as a child process.
    mcp.run()
