# Internal Knowledge Worker Skill

Purpose: retrieve evidence from the synthetic engineering knowledge base.

The single MCP tool is `search_knowledge`.

The tool runs the internal hybrid RAG pipeline:
Chroma dense retrieval + BM25 keyword retrieval -> RRF -> CrossEncoder reranking.

Use multiple query variants when they represent genuinely different angles.
Do not rely on metadata filters.
