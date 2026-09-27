"""Small persistent engineer-memory store.

BEGINNER IDEA
--------------
This is the engineer's notebook.  It stores only durable facts that LLM1
explicitly extracted from the engineer's own input.  Search uses SQLite FTS5,
not another LLM.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from config import MAX_MEMORY_FACTS_PER_TURN, MEMORY_DB_PATH, MEMORY_TOP_K


class MemoryStore:
    """SQLite + FTS5 store for durable engineer-specific facts."""

    def __init__(self, path: str | Path = MEMORY_DB_PATH):
        # PURPOSE: Create the parent directory and initialize the database schema.
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection.

        NEXT: _initialize(), save(), search(), or recent().
        """
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        """Create the memory and full-text-search tables if needed.

        NEXT: save() when new facts are written or search() when facts are recalled.
        """
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    engineer_id TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    person TEXT,
                    team TEXT,
                    topic TEXT,
                    importance TEXT NOT NULL,
                    source_turn INTEGER,
                    source_text TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(engineer_id, fact)
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    fact, person, team, topic,
                    content='memories', content_rowid='id'
                )
                """
            )
            # PURPOSE: Keep the FTS index aligned with the relational source table.
            conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")

    @staticmethod
    def _fts_query(query: str) -> str:
        """Turn free text into a safe OR-style FTS5 query.

        WHY: FTS5 expects a search expression. We quote individual words so punctuation
        from a user's conversation does not become FTS syntax.
        """
        words = []
        for raw in (query or "").replace('"', " ").split():
            cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in "_-.")
            if cleaned:
                words.append(cleaned[:80])
        return " OR ".join(f'"{word}"' for word in words[:16]) or '"memory"'

    def save(
        self,
        engineer_id: str,
        facts: list[dict[str, Any]],
        source_turn: int | None = None,
        source_text: str = "",
    ) -> int:
        """Persist a small number of durable facts for one engineer.

        PURPOSE:
            Remember useful facts such as "Paul from DevOps said..." across threads.

        NEXT:
            End of the current graph turn.
        """
        saved = 0
        clean_facts = facts[:MAX_MEMORY_FACTS_PER_TURN]
        with self._connect() as conn:
            for fact in clean_facts:
                text = str(fact.get("fact", "")).strip()
                if len(text) < 5:
                    continue
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO memories(
                        engineer_id, fact, person, team, topic, importance,
                        source_turn, source_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        engineer_id,
                        text,
                        fact.get("person"),
                        fact.get("team"),
                        fact.get("topic"),
                        fact.get("importance", "medium"),
                        source_turn,
                        source_text[:4000],
                    ),
                )
                saved += max(cursor.rowcount, 0)

            if saved:
                conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
        return saved

    def search(self, engineer_id: str, query: str, top_k: int = MEMORY_TOP_K) -> list[dict]:
        """Search this engineer's memory and return the most relevant facts.

        PURPOSE:
            Give the Planner historical context before it decides which workers to invoke.

        NEXT:
            src/graph/workflow.py -> planner_node().
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT m.id, m.engineer_id, m.fact, m.person, m.team, m.topic,
                       m.importance, m.source_turn, m.source_text, m.created_at
                FROM memories_fts
                JOIN memories m ON m.id = memories_fts.rowid
                WHERE m.engineer_id = ? AND memories_fts MATCH ?
                ORDER BY bm25(memories_fts), m.id DESC
                LIMIT ?
                """,
                (engineer_id, self._fts_query(query), int(top_k)),
            ).fetchall()
        return [dict(row) for row in rows]

    def recent(self, engineer_id: str, top_k: int = MEMORY_TOP_K) -> list[dict]:
        """Return newest facts as a fallback when relevance search has no hits.

        NEXT: src/graph/workflow.py -> memory_recall_node().
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE engineer_id = ? ORDER BY id DESC LIMIT ?",
                (engineer_id, int(top_k)),
            ).fetchall()
        return [dict(row) for row in rows]
