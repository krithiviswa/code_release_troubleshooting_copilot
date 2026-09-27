"""Two-turn persistent-memory example: remember a named DevOps contact."""

from src.memory.store import MemoryStore


if __name__ == "__main__":
    store = MemoryStore("memory/demo_memory.sqlite")

    # Turn 1: the engineer explicitly tells us about Paul and a useful fact.
    store.save(
        "demo-engineer",
        [
            {
                "fact": "Paul from DevOps said the XLR release train was unavailable during the earlier release.",
                "person": "Paul",
                "team": "DevOps",
                "topic": "XLR release train",
                "importance": "high",
            }
        ],
    )

    # Turn 2: the exact previous sentence does not need to be pasted again.
    # The memory search can surface the relevant Paul/DevOps fact.
    print(store.search("demo-engineer", "DevOps XLR release train", top_k=5))
