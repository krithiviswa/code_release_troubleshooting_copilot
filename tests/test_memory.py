"""Persistent engineer memory tests."""
from pathlib import Path

from src.memory.store import MemoryStore


def test_engineer_memory_is_persistent_and_searchable(tmp_path: Path):
    path = tmp_path / "memory.sqlite"
    first = MemoryStore(path)
    first.save(
        "engineer-1",
        [{
            "fact": "Paul from DevOps said to verify the XLR release train before retrying the deployment.",
            "person": "Paul",
            "team": "DevOps",
            "topic": "XLR release train",
            "importance": "high",
        }],
        source_turn=2,
        source_text="I checked with Paul from DevOps and he recommended verifying the XLR release train.",
    )

    second = MemoryStore(path)
    results = second.search("engineer-1", "DevOps XLR release train")
    assert results
    assert results[0]["person"] == "Paul"
    assert results[0]["source_turn"] == 2
