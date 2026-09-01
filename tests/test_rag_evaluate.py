import json

import pytest

from app.rag.evaluate import QueryResult, load_dataset, score_query, summarize


def _result(ranked, relevant, genres, expected, seconds=0.0):
    return QueryResult(
        query_id="q",
        ranked_ids=ranked,
        relevant=set(relevant),
        ranked_genres=genres,
        expected_genres=set(expected),
        seconds=seconds,
    )


def test_recall_counts_relevant_ids_found():
    assert _result([1, 2, 3], [2, 4], [], []).recall == 0.5


def test_recall_is_zero_without_judgements():
    assert _result([1, 2], [], [], []).recall == 0.0


def test_reciprocal_rank_uses_the_first_hit():
    assert _result([9, 9, 3], [3], [], []).reciprocal_rank == pytest.approx(1 / 3)
    assert _result([9], [3], [], []).reciprocal_rank == 0.0


def test_genre_precision_counts_candidates_overlapping_the_neighbourhood():
    result = _result(
        [1, 2, 3, 4],
        [],
        [["Horror"], ["Drama", "Comedy"], ["Western"], ["Thriller"]],
        ["Horror", "Thriller"],
    )
    assert result.genre_precision == 0.5


def test_genre_precision_is_case_insensitive():
    assert _result([1], [], [["science fiction"]], ["Science Fiction"]).genre_precision == 1.0


def test_genre_precision_is_zero_without_expectations():
    assert _result([1], [], [["Horror"]], []).genre_precision == 0.0


def test_summarize_averages_across_queries():
    totals = summarize([
        _result([1], [1], [["Horror"]], ["Horror"], seconds=2.0),
        _result([2], [1], [["Comedy"]], ["Horror"], seconds=4.0),
    ])
    assert totals["recall"] == 0.5
    assert totals["genre_precision"] == 0.5
    assert totals["hit_rate"] == 0.5
    assert totals["seconds"] == 3.0


def test_summarize_handles_no_results():
    assert summarize([])["recall"] == 0.0


def test_score_query_truncates_to_k():
    query = {"id": "q", "mood": "m", "relevant": [1], "expected_genres": ["Drama"]}
    retriever = lambda mood, k: (
        [f"T\nGenres: Drama\nOverview: o" for _ in range(5)],
        [{"tmdb_id": i} for i in range(5)],
    )
    result = score_query(query, retriever, k=3)
    assert len(result.ranked_ids) == 3
    assert len(result.ranked_genres) == 3


def test_shipped_dataset_is_well_formed():
    queries = load_dataset()
    assert len(queries) >= 10
    ids = [query["id"] for query in queries]
    assert len(ids) == len(set(ids))
    for query in queries:
        assert query["mood"].startswith("Selected tracks:")
        assert query["relevant"] and query["expected_genres"]


def test_missing_dataset_raises(tmp_path):
    from pathlib import Path

    with pytest.raises(RuntimeError):
        load_dataset(Path(tmp_path / "nope.json"))
