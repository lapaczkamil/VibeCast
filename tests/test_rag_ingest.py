from __future__ import annotations

from pathlib import Path

import httpx

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
    monkeypatch.setattr(ingest_mod.settings, "rag_discover_share", 0.7)
    genre_map = {18: "Drama"}

    def fake_discover(api_key: str, page: int, **kwargs) -> httpx.Response:
        assert page == 1
        return _page_response(
            [
                _movie_result(1, "Discover One"),
                _movie_result(2, "Discover Two"),
                _movie_result(3, "Discover Three"),
            ]
        )

    def fake_popular(api_key: str, page: int, **kwargs) -> httpx.Response:
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

    def fake_discover(api_key: str, page: int, **kwargs) -> httpx.Response:
        return _page_response(
            [
                _movie_result(1, "Has Plot"),
                _movie_result(2, "No Plot", overview=""),
            ]
        )

    def fake_popular(api_key: str, page: int, **kwargs) -> httpx.Response:
        return _page_response([_movie_result(3, "Popular")])

    monkeypatch.setattr(ingest_mod, "fetch_discover_movie_page_sync", fake_discover)
    monkeypatch.setattr(ingest_mod, "fetch_popular_page_sync", fake_popular)

    movies = ingest_mod._collect_movies("key", genre_map, target=2)
    assert [m["tmdb_id"] for m in movies] == [1, 3]


def test_collect_movies_discover_quota_uses_ceil(monkeypatch):
    """target=5 → discover quota ceil(0.7*5)=4, then 1 from popular."""
    monkeypatch.setattr(ingest_mod.settings, "rag_discover_share", 0.7)
    genre_map: dict[int, str] = {}
    discover_calls: list[int] = []

    def fake_discover(api_key: str, page: int, **kwargs) -> httpx.Response:
        discover_calls.append(page)
        return _page_response(
            [_movie_result(i, f"D{i}") for i in range(1, 6)],
            page=1,
            total_pages=1,
        )

    def fake_popular(api_key: str, page: int, **kwargs) -> httpx.Response:
        return _page_response([_movie_result(100, "P100")])

    monkeypatch.setattr(ingest_mod, "fetch_discover_movie_page_sync", fake_discover)
    monkeypatch.setattr(ingest_mod, "fetch_popular_page_sync", fake_popular)

    movies = ingest_mod._collect_movies("key", genre_map, target=5)
    assert len(movies) == 5
    assert [m["tmdb_id"] for m in movies[:4]] == [1, 2, 3, 4]
    assert movies[4]["tmdb_id"] == 100


def test_collect_stops_on_http_error_if_partial(monkeypatch):
    genre_map: dict[int, str] = {}
    pages = {"n": 0}

    def fake_discover(api_key: str, page: int, **kwargs) -> httpx.Response:
        pages["n"] += 1
        if pages["n"] == 1:
            return httpx.Response(
                200,
                json={
                    "page": 1,
                    "total_pages": 5,
                    "results": [
                        {
                            "id": 1,
                            "title": "A",
                            "release_date": "2010-01-01",
                            "overview": "Plot.",
                            "poster_path": "/a.jpg",
                            "vote_average": 8.0,
                            "genre_ids": [],
                        },
                        {
                            "id": 2,
                            "title": "B",
                            "release_date": "2010-01-01",
                            "overview": "Plot.",
                            "poster_path": "/b.jpg",
                            "vote_average": 8.0,
                            "genre_ids": [],
                        },
                    ],
                },
            )
        return httpx.Response(422, json={"status_message": "page too high"})

    def fake_popular(api_key: str, page: int, **kwargs) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "page": 1,
                "total_pages": 1,
                "results": [
                    {
                        "id": 10,
                        "title": "P",
                        "release_date": "2011-01-01",
                        "overview": "Plot.",
                        "poster_path": "/p.jpg",
                        "vote_average": 7.0,
                        "genre_ids": [],
                    },
                ],
            },
        )

    monkeypatch.setattr(ingest_mod, "fetch_discover_movie_page_sync", fake_discover)
    monkeypatch.setattr(ingest_mod, "fetch_popular_page_sync", fake_popular)

    movies = ingest_mod._collect_movies("key", genre_map, target=5)
    assert [m["tmdb_id"] for m in movies] == [1, 2, 10]


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


def test_run_ingest_resets_collection_before_upsert(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(ingest_mod.settings, "tmdb_api_key", "key")
    monkeypatch.setattr(ingest_mod, "ping_ollama_sync", lambda: True)
    monkeypatch.setattr(
        ingest_mod,
        "fetch_genre_list_sync",
        lambda key: httpx.Response(200, json={"genres": [{"id": 18, "name": "Drama"}]}),
    )
    monkeypatch.setattr(
        ingest_mod,
        "_collect_movies",
        lambda api_key, genre_map, target: [
            {
                "tmdb_id": 1,
                "title": "One",
                "year": "2010",
                "poster_path": "/x.jpg",
                "rating": 8.0,
                "overview": "Plot.",
                "genre_names": ["Drama"],
            }
        ],
    )
    monkeypatch.setattr(ingest_mod, "embed_documents", lambda docs: [[0.1, 0.2, 0.3] for _ in docs])

    def fake_reset() -> None:
        calls.append("reset")

    def fake_upsert(*args, **kwargs) -> None:
        calls.append("upsert")

    monkeypatch.setattr(ingest_mod, "reset_collection", fake_reset)
    monkeypatch.setattr(ingest_mod, "upsert_movies", fake_upsert)

    indexed = ingest_mod.run_ingest()
    assert indexed == 1
    assert calls[0] == "reset"
    assert "upsert" in calls


def test_build_document_keeps_overview_last():
    from app.rag.ingest import _build_document

    document = _build_document(
        "Blade Runner", "1982", ["Science Fiction"], "A blade runner hunts replicants.",
        ["dystopia", "cyberpunk"], "Man has made his match.",
    )
    assert document.splitlines() == [
        "Blade Runner (1982)",
        "Genres: Science Fiction",
        "Keywords: dystopia, cyberpunk",
        "Tagline: Man has made his match.",
        "Overview: A blade runner hunts replicants.",
    ]


def test_build_document_round_trips_through_the_existing_parsers():
    from app.rag.ingest import _build_document
    from app.rag.recommend import overview_from_document
    from app.reccobeats.rerank import genres_from_document

    document = _build_document(
        "Hereditary", "2018", ["Horror", "Drama"], "A family unravels after a death.",
        ["grief", "possession"], "Every family tree hides a secret.",
    )
    assert genres_from_document(document) == ["Horror", "Drama"]
    assert overview_from_document(document) == "A family unravels after a death."


def test_build_document_omits_empty_enrichment():
    from app.rag.ingest import _build_document

    document = _build_document("Dune", "1984", ["Science Fiction"], "Spice.", [], "")
    assert "Keywords:" not in document and "Tagline:" not in document


def test_build_document_caps_keyword_count():
    from app.rag.ingest import MAX_KEYWORDS, _build_document

    document = _build_document(
        "X", None, ["Drama"], "y", [f"kw{i}" for i in range(40)], "",
    )
    keywords = [
        line for line in document.splitlines() if line.startswith("Keywords:")
    ][0]
    assert keywords.count(",") == MAX_KEYWORDS - 1


def test_parse_enrichment_extracts_keywords_and_tagline():
    from app.rag.ingest import parse_enrichment

    keywords, tagline = parse_enrichment(
        {"tagline": "  A tagline.  ", "keywords": {"keywords": [
            {"name": "dystopia"}, {"name": "  "}, {"id": 1}, {"name": "cyberpunk"}]}}
    )
    assert keywords == ["dystopia", "cyberpunk"]
    assert tagline == "A tagline."


def test_parse_enrichment_tolerates_a_bare_payload():
    from app.rag.ingest import parse_enrichment

    assert parse_enrichment({}) == ([], "")
    assert parse_enrichment({"keywords": {}, "tagline": None}) == ([], "")


def _result(movie_id: int, rating, *, overview: str = "An overview."):
    return {
        "id": movie_id,
        "title": f"Movie {movie_id}",
        "overview": overview,
        "release_date": "2001-01-01",
        "poster_path": None,
        "vote_average": rating,
        "genre_ids": [],
    }


def _collect(results, monkeypatch, *, min_rating=7.0, limit=10):
    from app.rag import ingest

    monkeypatch.setattr(ingest.settings, "rag_min_rating", min_rating)
    movies: list = []
    ingest._append_from_results(
        results, movies=movies, seen_ids=set(), genre_map={}, limit=limit
    )
    return [movie["tmdb_id"] for movie in movies]


def test_rating_below_the_floor_is_dropped(monkeypatch):
    results = [_result(1, 6.9), _result(2, 7.0), _result(3, 8.4)]
    assert _collect(results, monkeypatch) == [2, 3]


def test_unrated_titles_are_dropped(monkeypatch):
    # /popular applies no filters, so unrated titles reach this gate.
    results = [_result(1, None), _result(2, 0), _result(3, 7.5)]
    assert _collect(results, monkeypatch) == [3]


def test_floor_is_configurable(monkeypatch):
    results = [_result(1, 6.2), _result(2, 7.1)]
    assert _collect(results, monkeypatch, min_rating=6.0) == [1, 2]


def test_rating_is_stored_rounded(monkeypatch):
    from app.rag import ingest

    monkeypatch.setattr(ingest.settings, "rag_min_rating", 7.0)
    movies: list = []
    ingest._append_from_results(
        [_result(1, 7.4499)], movies=movies, seen_ids=set(), genre_map={}, limit=5
    )
    assert movies[0]["rating"] == 7.4


def test_discover_page_carries_the_rating_floor():
    import respx
    from httpx import Response

    from app.movies.client import fetch_discover_movie_page_sync

    with respx.mock:
        route = respx.get("https://api.themoviedb.org/3/discover/movie").mock(
            return_value=Response(200, json={"results": [], "total_pages": 1})
        )
        fetch_discover_movie_page_sync("key", 1, vote_count_gte=500, vote_average_gte=7.0)
    assert route.calls[0].request.url.params["vote_average.gte"] == "7.0"


def test_discover_page_omits_the_floor_when_unset():
    import respx
    from httpx import Response

    from app.movies.client import fetch_discover_movie_page_sync

    with respx.mock:
        route = respx.get("https://api.themoviedb.org/3/discover/movie").mock(
            return_value=Response(200, json={"results": [], "total_pages": 1})
        )
        fetch_discover_movie_page_sync("key", 1)
    assert "vote_average.gte" not in route.calls[0].request.url.params
