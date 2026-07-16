import json

import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.main import app
from app.spotify import oauth
from app.spotify.oauth import TokenSet

client = TestClient(app)

TOKENS = TokenSet(
    access_token="access-abc", refresh_token="refresh-xyz", expires_at=None
)

CANDIDATE_METADATAS = [
    {
        "tmdb_id": 550,
        "title": "Fight Club",
        "year": "1999",
        "poster_path": "/poster.jpg",
    },
    {
        "tmdb_id": 27205,
        "title": "Inception",
        "year": "2010",
        "poster_path": None,
    },
]


def setup_function() -> None:
    oauth.clear_tokens()
    oauth.clear_pending_state()


def test_build_mood_query_includes_track_names():
    from app.rag.recommend import build_mood_query

    text = build_mood_query(
        now_playing_line="Now: Song by Artist",
        recent_lines=["Recent1"],
        top_track_lines=["Top1"],
        top_artist_lines=["ArtistA"],
    )
    assert "Song" in text and "Recent1" in text
    assert "Top1" in text and "ArtistA" in text


def test_parse_recommendation_json_extracts_items():
    from app.rag.recommend import parse_recommendation_json

    raw = '{"items":[{"tmdb_id":1,"title":"X","reason":"y"}]}'
    items = parse_recommendation_json(raw)
    assert items[0]["tmdb_id"] == 1


def test_recommend_unauthorized():
    response = client.post("/recommend")
    assert response.status_code == 401


def test_recommend_index_empty(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 0)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    response = client.post("/recommend")
    assert response.status_code == 503
    assert "ingest" in response.json()["detail"].lower()


def test_recommend_ollama_unreachable(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: False)
    response = client.post("/recommend")
    assert response.status_code == 503
    assert "ollama" in response.json()["detail"].lower()


@respx.mock
def test_recommend_happy_path(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    monkeypatch.setattr(
        "app.rag.recommend.embed_texts", lambda texts: [[0.1, 0.2, 0.3]]
    )
    monkeypatch.setattr(
        "app.rag.recommend.query_movies",
        lambda embedding, n_results: (
            ["doc1", "doc2"],
            CANDIDATE_METADATAS,
        ),
    )
    monkeypatch.setattr(
        "app.rag.recommend.chat_json",
        lambda prompt: json.dumps(
            {
                "mood_summary": "Dark, intense energy",
                "items": [
                    {
                        "tmdb_id": 550,
                        "title": "Fight Club",
                        "reason": "Matches your edgy top tracks",
                    },
                    {
                        "tmdb_id": 27205,
                        "title": "Inception",
                        "reason": "Mind-bending like your recent plays",
                    },
                ],
            }
        ),
    )

    response = client.post(
        "/recommend",
        json={
            "tracks": [
                {"id": "s1", "name": "Seed Song", "artists": ["Seed Artist"]}
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mood_summary"] == "Dark, intense energy"
    assert len(body["items"]) == 2
    assert body["items"][0]["tmdb_id"] == 550
    assert body["items"][0]["title"] == "Fight Club"
    assert body["items"][0]["year"] == "1999"
    assert (
        body["items"][0]["poster_url"]
        == "https://image.tmdb.org/t/p/w780/poster.jpg"
    )
    assert body["items"][0]["reason"] == "Matches your edgy top tracks"
    assert body["items"][1]["poster_url"] is None


@respx.mock
def test_recommend_drops_unknown_tmdb_ids(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    monkeypatch.setattr(
        "app.rag.recommend.embed_texts", lambda texts: [[0.1, 0.2, 0.3]]
    )
    monkeypatch.setattr(
        "app.rag.recommend.query_movies",
        lambda embedding, n_results: (["doc1"], [CANDIDATE_METADATAS[0]]),
    )
    monkeypatch.setattr(
        "app.rag.recommend.chat_json",
        lambda prompt: json.dumps(
            {
                "mood_summary": "Test mood",
                "items": [
                    {"tmdb_id": 550, "title": "Fight Club", "reason": "valid"},
                    {"tmdb_id": 99999, "title": "Fake", "reason": "invalid"},
                ],
            }
        ),
    )

    response = client.post(
        "/recommend",
        json={
            "tracks": [
                {"id": "s1", "name": "Seed Song", "artists": ["Seed Artist"]}
            ]
        },
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["tmdb_id"] == 550


@respx.mock
def test_recommend_parse_failure_502(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    monkeypatch.setattr(
        "app.rag.recommend.embed_texts", lambda texts: [[0.1, 0.2, 0.3]]
    )
    monkeypatch.setattr(
        "app.rag.recommend.query_movies",
        lambda embedding, n_results: (["doc1"], [CANDIDATE_METADATAS[0]]),
    )
    monkeypatch.setattr("app.rag.recommend.chat_json", lambda prompt: "not json")

    response = client.post(
        "/recommend",
        json={
            "tracks": [
                {"id": "s1", "name": "Seed Song", "artists": ["Seed Artist"]}
            ]
        },
    )
    assert response.status_code == 502


def test_recommend_with_seed_tracks_skips_listening_history(monkeypatch):
    oauth.set_tokens(TOKENS)
    respx.get("https://api.spotify.com/v1/me/player/currently-playing").mock(
        return_value=Response(204)
    )
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    captured: list[str] = []

    def fake_embed(texts):
        captured.extend(texts)
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr("app.rag.recommend.embed_texts", fake_embed)
    monkeypatch.setattr(
        "app.rag.recommend.query_movies",
        lambda emb, k: (["doc"], CANDIDATE_METADATAS[:1]),
    )
    monkeypatch.setattr(
        "app.rag.recommend.chat_json",
        lambda prompt: json.dumps(
            {
                "mood_summary": "Seeded",
                "items": [{"tmdb_id": 550, "title": "Fight Club", "reason": "x"}],
            }
        ),
    )

    with respx.mock:
        response = client.post(
            "/recommend",
            json={
                "tracks": [
                    {"id": "s1", "name": "Seed Song", "artists": ["Seed Artist"]}
                ]
            },
        )
    assert response.status_code == 200
    assert "Seed Song" in captured[0]
    assert "Recent1" not in captured[0]


def test_recommend_empty_tracks_no_now_playing_400(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    with respx.mock:
        respx.get("https://api.spotify.com/v1/me/player/currently-playing").mock(
            return_value=Response(204)
        )
        response = client.post("/recommend", json={"tracks": []})
    assert response.status_code == 400
    assert "select" in response.json()["detail"].lower()


def test_recommend_more_than_five_seeds_422(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    tracks = [
        {"id": f"t{i}", "name": f"S{i}", "artists": ["A"]} for i in range(6)
    ]
    response = client.post("/recommend", json={"tracks": tracks})
    assert response.status_code == 422


def _mock_spotify_context() -> None:
    respx.get("https://api.spotify.com/v1/me/player/currently-playing").mock(
        return_value=Response(204)
    )
    respx.get("https://api.spotify.com/v1/me/player/recently-played").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "played_at": "2026-01-01T00:00:00Z",
                        "track": {
                            "id": "t1",
                            "name": "Recent1",
                            "artists": [{"name": "Artist"}],
                            "album": {"name": "Album"},
                            "external_urls": {
                                "spotify": "https://open.spotify.com/track/t1"
                            },
                        },
                    }
                ]
            },
        )
    )
    respx.get("https://api.spotify.com/v1/me/top/tracks").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": "t2",
                        "name": "Top1",
                        "artists": [{"name": "Top Artist"}],
                        "album": {"name": "Album"},
                        "external_urls": {
                            "spotify": "https://open.spotify.com/track/t2"
                        },
                    }
                ]
            },
        )
    )
    respx.get("https://api.spotify.com/v1/me/top/artists").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": "a1",
                        "name": "ArtistA",
                        "genres": ["rock"],
                        "images": [],
                        "external_urls": {
                            "spotify": "https://open.spotify.com/artist/a1"
                        },
                    }
                ]
            },
        )
    )
