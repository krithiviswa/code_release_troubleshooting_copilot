"""Runtime helper for SQLite-backed LangGraph checkpointing."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from config import CHECKPOINT_DB_PATH
from src.graph.workflow import build_graph


@asynccontextmanager
async def checkpointed_graph():
    """Open a persistent SQLite checkpointer and yield a compiled graph.

    PURPOSE:
        Checkpointing lets a paused clarification request resume with the same thread_id.

    NEXT:
        app.py -> graph.ainvoke(...) or graph.ainvoke(Command(resume=...)).
    """
    Path(CHECKPOINT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    # AsyncSqliteSaver is appropriate for this local/learning project and supports
    # the async graph methods used by Gradio and the notebook.
    async with AsyncSqliteSaver.from_conn_string(str(CHECKPOINT_DB_PATH)) as saver:
        yield build_graph(checkpointer=saver)
