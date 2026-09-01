import pytest

from app.rag import bm25
from app.rag.bm25 import search_bm25, tokenize
from app.rag.hybrid import reciprocal_rank_fusion

DOCS = [
    "Blade Runner (1982)\nGenres: Science Fiction, Thriller\nOverview: A blade runner hunts replicants.",
    "Amelie (2001)\nGenres: Comedy, Romance\nOverview: A shy waitress decides to change the lives of those around her.",
    "Whiplash (2014)\nGenres: Drama, Music\nOverview: A young drummer is pushed to his limit by a ruthless instructor.",
]
METAS = [{"tmdb_id": 78}, {"tmdb_id": 194}, {"tmdb_id": 244786}]


@pytest.fixture(autouse=True)
def _fresh_index(monkeypatch):
    monkeypatch.setattr(bm25, "get_all_documents", lambda: (DOCS, METAS))
    monkeypatch.setattr(bm25, "count_movies", lambda: len(DOCS))
    bm25.reset_index()
    yield
    bm25.reset_index()


def _ranking(*tmdb_ids: int) -> tuple[list[str], list[dict]]:
    return [f"doc {i}" for i in tmdb_ids], [{"tmdb_id": i} for i in tmdb_ids]


def test_tokenize_folds_case_and_drops_punctuation():
    assert tokenize("Blade Runner (1982)\nGenres: Sci-Fi") == [
        "blade", "runner", "1982", "genres", "sci", "fi",
    ]


def test_bm25_finds_lexical_match_the_vector_search_would_miss():
    docs, metas = search_bm25("drummer instructor", 3)
    assert [meta["tmdb_id"] for meta in metas] == [244786]


def test_bm25_matches_on_the_genres_line():
    docs, metas = search_bm25("romance comedy", 3)
    assert metas[0]["tmdb_id"] == 194


def test_bm25_returns_nothing_when_no_term_overlaps():
    assert search_bm25("kalejdoskop wodospad", 3) == ([], [])


def test_bm25_respects_n_results():
    assert len(search_bm25("a", 1)[0]) <= 1


def test_bm25_index_rebuilds_when_collection_size_changes(monkeypatch):
    assert bm25.get_index().size == 3
    monkeypatch.setattr(bm25, "get_all_documents", lambda: (DOCS[:2], METAS[:2]))
    monkeypatch.setattr(bm25, "count_movies", lambda: 2)
    assert bm25.get_index().size == 2


def test_bm25_handles_empty_collection(monkeypatch):
    monkeypatch.setattr(bm25, "get_all_documents", lambda: ([], []))
    monkeypatch.setattr(bm25, "count_movies", lambda: 0)
    bm25.reset_index()
    assert search_bm25("anything", 3) == ([], [])


def test_rrf_rewards_agreement_between_retrievers():
    # 2 is only mid-ranked by the vector search, but both retrievers found it;
    # 1 tops the vector ranking and the lexical one never saw it.
    docs, metas = reciprocal_rank_fusion([_ranking(1, 2, 3), _ranking(2)], 3)
    assert [meta["tmdb_id"] for meta in metas] == [2, 1, 3]


def test_rrf_falls_back_to_the_single_ranking_when_one_is_empty():
    docs, metas = reciprocal_rank_fusion([_ranking(5, 6, 7), ([], [])], 3)
    assert [meta["tmdb_id"] for meta in metas] == [5, 6, 7]


def test_rrf_deduplicates_across_rankings():
    docs, metas = reciprocal_rank_fusion([_ranking(1, 2), _ranking(2, 1)], 10)
    assert sorted(meta["tmdb_id"] for meta in metas) == [1, 2]


def test_rrf_truncates_to_n_results():
    docs, metas = reciprocal_rank_fusion([_ranking(1, 2, 3, 4)], 2)
    assert len(metas) == 2 and len(docs) == 2


def test_rrf_is_deterministic_on_ties():
    tied = [_ranking(9, 8), _ranking(8, 9)]
    first = reciprocal_rank_fusion(tied, 2)[1]
    assert first == reciprocal_rank_fusion(tied, 2)[1]


def test_hybrid_search_is_dense_only_when_disabled(monkeypatch):
    from app.rag import hybrid

    calls: dict = {}

    def fake_dense(embedding, n_results):
        calls["n_results"] = n_results
        return _ranking(1, 2)

    monkeypatch.setattr(hybrid, "query_movies", fake_dense)
    monkeypatch.setattr(
        hybrid, "search_bm25", lambda *a: pytest.fail("lexical search must not run")
    )
    monkeypatch.setattr(hybrid.settings, "rag_hybrid_enabled", False)

    docs, metas = hybrid.hybrid_search("mood", [0.1], 2)
    assert [meta["tmdb_id"] for meta in metas] == [1, 2]
    assert calls["n_results"] == 2


def test_hybrid_search_widens_the_pool_before_fusing(monkeypatch):
    from app.rag import hybrid

    calls: dict = {}

    def fake_dense(embedding, n_results):
        calls["dense"] = n_results
        return _ranking(1, 2, 3)

    def fake_lexical(query, n_results):
        calls["lexical"] = n_results
        return _ranking(3)

    monkeypatch.setattr(hybrid, "query_movies", fake_dense)
    monkeypatch.setattr(hybrid, "search_bm25", fake_lexical)
    monkeypatch.setattr(hybrid.settings, "rag_hybrid_enabled", True)
    monkeypatch.setattr(hybrid.settings, "rag_hybrid_candidates", 32)

    docs, metas = hybrid.hybrid_search("mood", [0.1], 2)
    assert calls == {"dense": 32, "lexical": 32}
    assert [meta["tmdb_id"] for meta in metas] == [3, 1]
