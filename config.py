"""Central configuration for the Engineering Troubleshooting Copilot.

BEGINNER IDEA
--------------
A configuration value is a tuning knob.  We keep model names, chunk sizes,
retrieval counts, budgets, file paths and evaluation thresholds here so that
we can experiment without editing the application logic.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# PURPOSE: Load optional values from a local .env file before reading settings.
load_dotenv()

# PURPOSE: Keep project paths in one place so every module agrees on where files live.
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(PROJECT_ROOT / "chroma_db")))
MEMORY_DIR = Path(os.getenv("MEMORY_DIR", str(PROJECT_ROOT / "memory")))
MEMORY_DB_PATH = Path(os.getenv("MEMORY_DB_PATH", str(MEMORY_DIR / "engineer_memory.sqlite")))
CHECKPOINT_DB_PATH = Path(os.getenv("CHECKPOINT_DB_PATH", str(MEMORY_DIR / "checkpoints.sqlite")))
SKILLS_DIR = Path(os.getenv("SKILLS_DIR", str(PROJECT_ROOT / "skills")))

# PURPOSE: Start with the lower-cost model profile.
# NOTE: Free/trial availability depends on the API account.  The code does not
# assume that a particular model is permanently free.
MODEL_PROFILES = {
    "light": {
        "context_model": os.getenv("LIGHT_CONTEXT_MODEL", "gpt-5.4-nano"),
        "planner_model": os.getenv("LIGHT_PLANNER_MODEL", "gpt-5.4-nano"),
        "recommendation_model": os.getenv("LIGHT_RECOMMENDATION_MODEL", "gpt-5.4-nano"),
        "critic_model": os.getenv("LIGHT_CRITIC_MODEL", "gpt-5.4-nano"),
        "eval_judge_model": os.getenv("LIGHT_EVAL_JUDGE_MODEL", "gpt-5.4-nano"),
    },
    "advanced": {
        "context_model": os.getenv("ADV_CONTEXT_MODEL", "gpt-5.4-mini"),
        "planner_model": os.getenv("ADV_PLANNER_MODEL", "gpt-5.4-nano"),
        "recommendation_model": os.getenv("ADV_RECOMMENDATION_MODEL", "gpt-5.4-mini"),
        "critic_model": os.getenv("ADV_CRITIC_MODEL", "gpt-5.4-nano"),
        "eval_judge_model": os.getenv("ADV_EVAL_JUDGE_MODEL", "gpt-5.4-mini"),
    },
}
MODEL_PROFILE = os.getenv("MODEL_PROFILE", "light")
if MODEL_PROFILE not in MODEL_PROFILES:
    raise ValueError(f"Unknown MODEL_PROFILE={MODEL_PROFILE!r}. Use one of {list(MODEL_PROFILES)}")

_active_models = MODEL_PROFILES[MODEL_PROFILE]
CONTEXT_MODEL = os.getenv("CONTEXT_MODEL", _active_models["context_model"])
PLANNER_MODEL = os.getenv("PLANNER_MODEL", _active_models["planner_model"])
RECOMMENDATION_MODEL = os.getenv("RECOMMENDATION_MODEL", _active_models["recommendation_model"])
CRITIC_MODEL = os.getenv("CRITIC_MODEL", _active_models["critic_model"])
EVAL_JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", _active_models["eval_judge_model"])
# Optional temperature. GPT-5 reasoning models may reject temperature when reasoning is enabled, so leave this blank by default.
raw_temperature = os.getenv("MODEL_TEMPERATURE", "").strip()
MODEL_TEMPERATURE = float(raw_temperature) if raw_temperature else None

# PURPOSE: Internal RAG model configuration.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L6-v2")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "engineering_knowledge")

# PURPOSE: Document-aware chunking knobs.
# Chunk size is approximate because we preserve logical boundaries whenever possible.
CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "1800"))
# Very small chunks can lose context, so the chunker tries not to leave tiny orphans.
CHUNK_MIN_CHARS = int(os.getenv("CHUNK_MIN_CHARS", "300"))
# Overlap repeats a small tail of the previous chunk so context is not lost at a boundary.
CHUNK_OVERLAP_CHARS = int(os.getenv("CHUNK_OVERLAP_CHARS", "250"))
# Conversation chunks overlap by a whole message block rather than arbitrary characters.
CONVERSATION_OVERLAP_BLOCKS = int(os.getenv("CONVERSATION_OVERLAP_BLOCKS", "1"))

# PURPOSE: Hybrid retrieval knobs.
DENSE_CANDIDATE_K = int(os.getenv("DENSE_CANDIDATE_K", "16"))
BM25_CANDIDATE_K = int(os.getenv("BM25_CANDIDATE_K", "16"))
FINAL_K = int(os.getenv("FINAL_K", "8"))
# RRF_K is the tuning constant in 1/(RRF_K + rank).  Higher values make rank differences less dramatic.
RRF_K = int(os.getenv("RRF_K", "60"))
# LLM1/planner may propose several internal search views of the same problem.
MAX_RETRIEVAL_QUERIES = int(os.getenv("MAX_RETRIEVAL_QUERIES", "5"))
MAX_EXTERNAL_QUERIES = int(os.getenv("MAX_EXTERNAL_QUERIES", "3"))

# PURPOSE: Input and runtime budgets.
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "60000"))
MAX_HISTORY_CHARS = int(os.getenv("MAX_HISTORY_CHARS", "60000"))
MAX_EVIDENCE_ITEMS = int(os.getenv("MAX_EVIDENCE_ITEMS", "24"))
MAX_EVIDENCE_CHARS = int(os.getenv("MAX_EVIDENCE_CHARS", "12000"))
MCP_TIMEOUT_SECONDS = float(os.getenv("MCP_TIMEOUT_SECONDS", "60"))
MAX_TOOL_RESULT_CHARS = int(os.getenv("MAX_TOOL_RESULT_CHARS", "9000"))
MAX_WEB_RESULTS = int(os.getenv("MAX_WEB_RESULTS", "5"))
MAX_WEB_RESULT_CHARS = int(os.getenv("MAX_WEB_RESULT_CHARS", "2500"))
# PURPOSE: Bound total MCP activity for one graph turn.
MAX_MCP_CALLS = int(os.getenv("MAX_MCP_CALLS", "12"))
# PURPOSE: Unit/evaluation runs can use deterministic synthetic web observations without calling the live internet.
MOCK_WEB_SEARCH = os.getenv("MOCK_WEB_SEARCH", "true").lower() == "true" #mock web search turned on
MAX_REACT_STEPS = int(os.getenv("MAX_REACT_STEPS", "4"))
MAX_DYNAMIC_WORKERS = 2  # Fixed by design: Internal RAG + External Web Research.
MAX_CLARIFICATIONS = int(os.getenv("MAX_CLARIFICATIONS", "2"))
MAX_REFLECTION_ROUNDS = int(os.getenv("MAX_REFLECTION_ROUNDS", "2"))

# PURPOSE: Persistent memory and LangGraph checkpointing.
MEMORY_TOP_K = int(os.getenv("MEMORY_TOP_K", "5"))
MAX_MEMORY_FACTS_PER_TURN = int(os.getenv("MAX_MEMORY_FACTS_PER_TURN", "5"))
DEFAULT_ENGINEER_ID = os.getenv("DEFAULT_ENGINEER_ID", "demo-engineer")
DEFAULT_THREAD_ID = os.getenv("DEFAULT_THREAD_ID", "demo-thread")
LANGGRAPH_RECURSION_LIMIT = int(os.getenv("LANGGRAPH_RECURSION_LIMIT", "40"))

# PURPOSE: Only two MCP capabilities are exposed by the application.
AVAILABLE_TOOLS = ["search_knowledge", "search_web"]
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# PURPOSE: Evaluation knobs.
EVAL_MAX_CASES = int(os.getenv("EVAL_MAX_CASES", "12"))
EVAL_ENABLE_LLM_JUDGE = os.getenv("EVAL_ENABLE_LLM_JUDGE", "false").lower() == "true" # turned off LLM as judge to save tokens
EVAL_JUDGE_THRESHOLD = float(os.getenv("EVAL_JUDGE_THRESHOLD", "0.60"))
EVAL_LLM_METRIC_LIMIT = int(os.getenv("EVAL_LLM_METRIC_LIMIT", "6"))
# These thresholds belong in config because they define what counts as a deterministic match.
EVAL_ACTION_SIMILARITY_THRESHOLD = float(os.getenv("EVAL_ACTION_SIMILARITY_THRESHOLD", "0.45"))
EVAL_REPEAT_SIMILARITY_THRESHOLD = float(os.getenv("EVAL_REPEAT_SIMILARITY_THRESHOLD", "0.60"))
EVAL_CASE_ACTION_COVERAGE_THRESHOLD = float(os.getenv("EVAL_CASE_ACTION_COVERAGE_THRESHOLD", "0.50"))
EVAL_CASE_SOURCE_COVERAGE_THRESHOLD = float(os.getenv("EVAL_CASE_SOURCE_COVERAGE_THRESHOLD", "0.50"))

# PURPOSE: Stopwords are ordinary words that contribute little to our simple regression matcher.
# Example: "check the JVM restart" -> the matcher focuses more on check/JVM/restart than "the".
# --------------------------------------------------------------------------
# Telemetry / tracing
# --------------------------------------------------------------------------
# LangSmith was NOT previously wired into this project. It needs almost no
# code changes to trace this graph: every LLM call goes through
# langchain_openai.ChatOpenAI (see src/llm.py) and the graph itself is a
# LangGraph StateGraph, both of which LangSmith auto-instruments through
# LangChain's callback system as soon as these env vars are set. This block
# only sets a sensible project-name default; the person still needs their
# own LANGCHAIN_API_KEY (a free LangSmith account) for tracing to activate -
# with no key set, LANGCHAIN_TRACING_V2=true is a silent no-op, not an error.
LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGCHAIN_PROJECT", "engineering-troubleshooting-copilot"))

# Local, dependency-free complement to LangSmith: every LLM call and MCP call
# already carries usage/timing (see src/llm.py, src/mcp_client.py); this flag
# controls whether that telemetry is also appended to a local JSONL file via
# src/telemetry.py, so token/latency history is inspectable even without a
# LangSmith account, and stays available offline (e.g. in Colab with no
# outbound network access at all).
ENABLE_LOCAL_TELEMETRY = os.getenv("ENABLE_LOCAL_TELEMETRY", "true").lower() == "true"
TELEMETRY_LOG_PATH = os.getenv("TELEMETRY_LOG_PATH", str(MEMORY_DIR / "telemetry.jsonl"))

EVAL_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
        "is", "are", "was", "be", "this", "that", "it", "as", "by", "from",
        "at", "after", "before", "into", "then", "than", "has", "have", "had",
    }
)


def active_models() -> dict[str, str]:
    """Return selected models so the UI and README can display the active configuration.

    NEXT: app.py -> build_ui()
    """
    return {
        "profile": MODEL_PROFILE,
        "context_model": CONTEXT_MODEL,
        "planner_model": PLANNER_MODEL,
        "recommendation_model": RECOMMENDATION_MODEL,
        "critic_model": CRITIC_MODEL,
        "eval_judge_model": EVAL_JUDGE_MODEL,
    }
