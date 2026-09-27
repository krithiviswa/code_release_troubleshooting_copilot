from src.rag.fusion import reciprocal_rank_fusion


def item(chunk_id):
    return {"chunk_id": chunk_id, "content": chunk_id, "metadata": {}}


def test_rrf_prefers_consistently_high_ranked_item():
    dense = [item("A"), item("B"), item("C")]
    bm25 = [item("B"), item("C"), item("A")]
    fused = reciprocal_rank_fusion([dense, bm25], k=60)
    assert fused[0]["chunk_id"] in {"A", "B"}
    assert fused[0]["rrf_score"] > fused[-1]["rrf_score"]


def test_rrf_can_fuse_more_than_two_rankings():
    lists = [
        [item("A"), item("B")],
        [item("A"), item("C")],
        [item("A"), item("D")],
    ]
    fused = reciprocal_rank_fusion(lists, k=60)
    assert fused[0]["chunk_id"] == "A"
