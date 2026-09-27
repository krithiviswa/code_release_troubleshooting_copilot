# Chunking strategy guide

## Why different strategies?

A runbook has headings and procedures. A JIRA ticket is a record. A triage history is a conversation. Cutting all three every N characters can separate information that naturally belongs together.

## Runbook

`ingestion.py` separates Markdown sections into logical records.

`chunking.py` then uses `RecursiveCharacterTextSplitter` with this preference:

```text
paragraph -> line -> sentence -> word -> character
```

This keeps the largest sensible boundary intact before falling back to smaller pieces.

## Triage conversation

`triageconversations.md` is intentionally one continuous history. The chunker first identifies blank-line-separated message blocks and accumulates whole blocks until the configured size is reached.

The next chunk can repeat the last `CONVERSATION_OVERLAP_BLOCKS` message blocks. This is better than copying an arbitrary 250 characters because the repeated unit is a complete conversational message.

## JIRA

Top-level ticket headings create logical records. Each ticket is then recursively split only when it is too large.

## Configuration knobs

```text
CHUNK_MAX_CHARS
    Maximum approximate chunk length.

CHUNK_MIN_CHARS
    Helps avoid very small trailing conversation chunks.

CHUNK_OVERLAP_CHARS
    Character overlap used by recursive fallback/structured documents.

CONVERSATION_OVERLAP_BLOCKS
    Number of whole speaker/message blocks repeated between conversation chunks.
```

These are constants because they are tuning parameters. Changing them changes the retrieval experiment; the retrieval code itself does not need to be rewritten.
