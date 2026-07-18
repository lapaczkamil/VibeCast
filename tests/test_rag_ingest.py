from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from app.rag import ingest as ingest_mod
from app.rag import store as store_mod


def _movie_result(movie_id: int, title: str, overview: str = "Plot.") -> dict:
    return {
        "id": movie_id,
        "title": title,
        "release_date": "2010-01-01",
        "overview": overview,
        "poster_path": f"/{movie_id}.jpg",
        "vote_average": 8.0,
        "genre_ids": [18],
    }


def _page_response(results: list[dict], page: int = 1, total_pages: int = 1) -> httpx.Response:
    return httpx.Response(
        200,
        json={"page": page, "total_pages": total_pages, "results": results},
    )


def test_collect_movies_prefers_discover_then_popular(monkeypatch):
    genre_map = {18: "Drama"}

    def fake_discover(api_key: str, page: int) -> httpx.Response:
        assert page == 1
        return _page_response(
            [
                _movie_result(1, "Discover One"),
                _movie_result(2, "Discover Two"),
                _movie_result(3, "Discover Three"),
            ]
        )

    def fake_popular(api_key: str, page: int) -> httpx.Response:
        assert page == 1
        return _page_response(
            [
                _movie_result(2, "Dup Popular"),  # already from discover
                _movie_result(10, "Popular Ten"),
                _movie_result(11, "Popular Eleven"),
            ]
        )

    monkeypatch.setattr(ingest_mod, "fetch_discover_movie_page_sync", fake_discover)
    monkeypatch.setattr(ingest_mod, "fetch_popular_page_sync", fake_popular)

    movies = ingest_mod._collect_movies("key", genre_map, target=4)
    ids = [m["tmdb_id"] for m in movies]
    assert ids == [1, 2, 3, 10]
    assert all(m["overview"] for m in movies)
    assert movies[0]["genre_names"] == ["Drama"]


def test_collect_movies_skips_empty_overview(monkeypatch):
    genre_map: dict[int, str] = {}

    def fake_discover(api_key: str, page: int) -> httpx.Response:
        return _page_response(
            [
                _movie_result(1, "Has Plot"),
                _movie_result(2, "No Plot", overview=""),
            ]
        )

    def fake_popular(api_key: str, page: int) -> httpx.Response:
        return _page_response([_movie_result(3, "Popular")])

    monkeypatch.setattr(ingest_mod, "fetch_discover_movie_page_sync", fake_discover)
    monkeypatch.setattr(ingest_mod, "fetch_popular_page_sync", fake_popular)

    movies = ingest_mod._collect_movies("key", genre_map, target=2)
    assert [m["tmdb_id"] for m in movies] == [1, 3]


def test_collect_movies_discover_quota_uses_ceil(monkeypatch):
    """target=5 → discover quota ceil(0.7*5)=4, then 1 from popular."""
    genre_map: dict[int, str] = {}
    discover_calls: list[int] = []

    def fake_discover(api_key: str, page: int) -> httpx.Response:
        discover_calls.append(page)
        return _page_response(
            [_movie_result(i, f"D{i}") for i in range(1, 6)],
            page=1,
            total_pages=1,
        )

    def fake_popular(api_key: str, page: int) -> httpx.Response:
        return _page_response([_movie_result(100, "P100")])

    monkeypatch.setattr(ingest_mod, "fetch_discover_movie_page_sync", fake_discover)
    monkeypatch.setattr(ingest_mod, "fetch_popular_page_sync", fake_popular)

    movies = ingest_mod._collect_movies("key", genre_map, target=5)
    assert len(movies) == 5
    assert [m["tmdb_id"] for m in movies[:4]] == [1, 2, 3, 4]
    assert movies[4]["tmdb_id"] == 100


def test_reset_collection_wipes_and_recreates(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(store_mod.settings, "rag_chroma_path", str(tmp_path / "chroma"))
    monkeypatch.setattr(store_mod.settings, "rag_collection", "movies_test")
    store_mod._client = None

    store_mod.upsert_movies(
        ids=["1"],
        documents=["Doc"],
        metadatas=[{"tmdb_id": 1, "title": "A", "year": "", "poster_path": "", "rating": 0.0}],
        embeddings=[[0.1, 0.2, 0.3]],
    )
    assert store_mod.count_movies() == 1

    store_mod.reset_collection()
    assert store_mod.count_movies() == 0

    store_mod.upsert_movies(
        ids=["2"],
        documents=["Doc2"],
        metadatas=[{"tmdb_id": 2, "title": "B", "year": "", "poster_path": "", "rating": 0.0}],
        embeddings=[[0.3, 0.2, 0.1]],
    )
    assert store_mod.count_movies() == 1
