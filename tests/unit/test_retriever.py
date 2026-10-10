from hermes.rag.retriever import search_regulations


def test_search_regulations_empty_query():
    assert search_regulations("") == []


def test_search_regulations_not_found():
    assert search_regulations("asdfasdfasdf") == []


def test_search_regulations_found():
    results = search_regulations("tín chỉ")
    assert len(results) > 0
    # Should match Article 10 (tín chỉ) or 25 (tín chỉ)
    assert results[0]["article"] in [10, 25]
    assert "content" in results[0]
    assert "document" in results[0]


def test_search_regulations_top_k():
    results = search_regulations("điểm trung bình", top_k=1)
    assert len(results) == 1
    # Both 18 and 25 have this, just check length
