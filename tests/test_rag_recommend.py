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
        "rating": 8.4,
    },
    {
        "tmdb_id": 27205,
        "title": "Inception",
        "year": "2010",
        "poster_path": None,
        "rating": 8.8,
    },
]


def setup_function() -> None:
    from app.reccobeats import client as rb_client

    oauth.clear_tokens()
    oauth.clear_pending_state()
    rb_client.clear_audio_features_cache()


def _mock_reccobeats_offline() -> None:
    respx.get("https://api.reccobeats.com/v1/audio-features").mock(
        return_value=Response(404)
    )


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


def test_overview_from_document():
    from app.rag.recommend import overview_from_document

    doc = "Title (2000)\nGenres: Drama\nOverview: A quiet story about loss."
    assert overview_from_document(doc) == "A quiet story about loss."
    assert overview_from_document("no overview here") == ""


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
    _mock_reccobeats_offline()
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    monkeypatch.setattr(
        "app.rag.recommend.embed_query", lambda text: [0.1, 0.2, 0.3]
    )
    monkeypatch.setattr(
        "app.rag.recommend.hybrid_search",
        lambda mood_query, embedding, n_results: (
            [
                "Fight Club (1999)\nGenres: Drama\nOverview: An insomniac office worker forms an underground fight club.",
                "Inception (2010)\nGenres: Science Fiction\nOverview: A thief who steals corporate secrets through dream-sharing.",
            ],
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
    assert body["items"][0]["rating"] == 8.4
    assert (
        body["items"][0]["poster_url"]
        == "https://image.tmdb.org/t/p/w780/poster.jpg"
    )
    assert body["items"][0]["reason"] == "Matches your edgy top tracks"
    assert "fight club" in body["items"][0]["overview"].lower()
    assert body["items"][1]["poster_url"] is None
    assert "dream" in body["items"][1]["overview"].lower()


@respx.mock
def test_recommend_drops_unknown_tmdb_ids(monkeypatch):
    oauth.set_tokens(TOKENS)
    _mock_reccobeats_offline()
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    monkeypatch.setattr(
        "app.rag.recommend.embed_query", lambda text: [0.1, 0.2, 0.3]
    )
    monkeypatch.setattr(
        "app.rag.recommend.hybrid_search",
        lambda mood_query, embedding, n_results: (["doc1"], [CANDIDATE_METADATAS[0]]),
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
    _mock_reccobeats_offline()
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    monkeypatch.setattr(
        "app.rag.recommend.embed_query", lambda text: [0.1, 0.2, 0.3]
    )
    monkeypatch.setattr(
        "app.rag.recommend.hybrid_search",
        lambda mood_query, embedding, n_results: (["doc1"], [CANDIDATE_METADATAS[0]]),
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

    def fake_embed(text):
        captured.extend([text])
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr("app.rag.recommend.embed_query", fake_embed)
    monkeypatch.setattr(
        "app.rag.recommend.hybrid_search",
        lambda mood_query, emb, k: (["doc"], CANDIDATE_METADATAS[:1]),
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
        _mock_reccobeats_offline()
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


@respx.mock
def test_recommend_enriches_mood_with_reccobeats(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)

    captured: dict = {}

    def fake_embed(text):
        captured["mood"] = text
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr("app.rag.recommend.embed_query", fake_embed)

    docs = [
        "A\nGenres: Drama\nOverview: a",
        "B\nGenres: Action, Thriller\nOverview: b",
    ]
    metas = [
        {
            "tmdb_id": 1,
            "title": "A",
            "year": "2000",
            "poster_path": "",
            "rating": 7.0,
        },
        {
            "tmdb_id": 2,
            "title": "B",
            "year": "2001",
            "poster_path": "",
            "rating": 7.1,
        },
    ]

    def fake_query(mood_query, embedding, n_results):
        captured["n_results"] = n_results
        return (docs, metas)

    monkeypatch.setattr("app.rag.recommend.hybrid_search", fake_query)

    def fake_chat(prompt: str) -> str:
        captured["prompt"] = prompt
        return json.dumps(
            {
                "mood_summary": "Intense",
                "items": [{"tmdb_id": 2, "title": "B", "reason": "energy match"}],
            }
        )

    monkeypatch.setattr("app.rag.recommend.chat_json", fake_chat)

    respx.get("https://api.reccobeats.com/v1/audio-features").mock(
        return_value=Response(
            200,
            json={
                "content": [
                    {
                        "energy": 0.95,
                        "valence": 0.5,
                        "danceability": 0.3,
                        "acousticness": 0.1,
                        "tempo": 140.0,
                    }
                ]
            },
        )
    )

    response = client.post(
        "/recommend",
        json={"tracks": [{"id": "seed1", "name": "Loud", "artists": ["X"]}]},
    )
    assert response.status_code == 200
    assert "Audio profile:" in captured["mood"]
    assert (
        "energy" in captured["mood"].lower()
        or "intense" in captured["mood"].lower()
        or "high energy" in captured["mood"].lower()
    )
    assert captured["n_results"] == 16
    assert captured["prompt"].index("tmdb_id=2") < captured["prompt"].index("tmdb_id=1")


@respx.mock
def test_recommend_soft_fails_reccobeats(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)

    captured: dict = {}

    def fake_embed(text):
        captured["mood"] = text
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr("app.rag.recommend.embed_query", fake_embed)

    def fake_query(mood_query, embedding, n_results):
        captured["n_results"] = n_results
        return (["doc1"], [CANDIDATE_METADATAS[0]])

    monkeypatch.setattr("app.rag.recommend.hybrid_search", fake_query)
    monkeypatch.setattr(
        "app.rag.recommend.chat_json",
        lambda prompt: json.dumps(
            {
                "mood_summary": "Fallback mood",
                "items": [
                    {"tmdb_id": 550, "title": "Fight Club", "reason": "still works"},
                ],
            }
        ),
    )

    respx.get("https://api.reccobeats.com/v1/audio-features").mock(
        return_value=Response(500, text="nope")
    )

    response = client.post(
        "/recommend",
        json={"tracks": [{"id": "seed1", "name": "Loud", "artists": ["X"]}]},
    )
    assert response.status_code == 200
    assert "Audio profile:" not in captured["mood"]
    assert captured["n_results"] == 8


@respx.mock
def test_recommend_retrieves_with_the_hypothetical_document(monkeypatch):
    """The rewrite, not the raw mood, is what reaches the index."""
    from app.rag.hyde import Hypothetical

    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)

    captured: dict = {}

    async def fake_lyrics(track_name, artists):
        captured["lyrics_args"] = (track_name, artists)
        return "driving through the city at night"

    monkeypatch.setattr("app.rag.recommend.fetch_lyrics", fake_lyrics)
    monkeypatch.setattr(
        "app.rag.recommend.hypothetical_document",
        lambda mood, lyrics=None: (
            captured.setdefault("lyrics", lyrics),
            Hypothetical(
                query="Genres: Crime\nOverview: A courier drives at night.",
                mood_summary="neon melancholy",
                generated=True,
            ),
        )[1],
    )

    def fake_embed(text):
        captured["embedded"] = text
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr("app.rag.recommend.embed_query", fake_embed)
    monkeypatch.setattr(
        "app.rag.recommend.hybrid_search",
        lambda mood_query, embedding, k: (
            captured.setdefault("retrieval_query", mood_query),
            (["doc"], CANDIDATE_METADATAS[:1]),
        )[1],
    )
    monkeypatch.setattr(
        "app.rag.recommend.chat_json",
        lambda prompt: json.dumps({"mood_summary": "", "items": []}),
    )

    response = client.post(
        "/recommend",
        json={"tracks": [{"id": "seed1", "name": "Nightcall", "artists": ["Kavinsky"]}]},
    )
    assert response.status_code == 200
    assert captured["embedded"].startswith("Genres: Crime")
    assert captured["retrieval_query"].startswith("Genres: Crime")
    # An empty summary from the selector falls back to the rewrite's own.
    assert response.json()["mood_summary"] == "neon melancholy"
    # The lyrics are looked up for the seed track and handed to the rewrite.
    assert captured["lyrics_args"] == ("Nightcall", ["Kavinsky"])
    assert captured["lyrics"] == "driving through the city at night"
