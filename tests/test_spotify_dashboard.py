import asyncio

import respx
from httpx import ASGITransport, AsyncClient, Response
from fastapi.testclient import TestClient

from app.main import app
from app.spotify import oauth
from app.spotify.oauth import TokenSet


client = TestClient(app)


def setup_function() -> None:
    oauth.clear_tokens()
    oauth.clear_pending_state()


def test_me_unauthorized_without_token():
    response = client.get("/spotify/me")
    assert response.status_code == 401


@respx.mock
def test_me_maps_profile():
    oauth.set_tokens(
        TokenSet(access_token="access-abc", refresh_token="refresh-xyz", expires_at=None)
    )
    respx.get("https://api.spotify.com/v1/me").mock(
        return_value=Response(
            200,
            json={
                "id": "user123",
                "display_name": "Test User",
                "images": [{"url": "https://i.scdn.co/image/avatar"}],
                "country": "US",
                "product": "premium",
            },
        )
    )
    response = client.get("/spotify/me")
    assert response.status_code == 200
    assert response.json() == {
        "id": "user123",
        "display_name": "Test User",
        "image_url": "https://i.scdn.co/image/avatar",
        "country": "US",
        "product": "premium",
    }
    assert "access-abc" not in str(response.json())


@respx.mock
def test_currently_playing_empty_204():
    oauth.set_tokens(
        TokenSet(access_token="access-abc", refresh_token="refresh-xyz", expires_at=None)
    )
    respx.get("https://api.spotify.com/v1/me/player/currently-playing").mock(
        return_value=Response(204)
    )
    response = client.get("/spotify/currently-playing")
    assert response.status_code == 200
    assert response.json() == {"is_playing": False, "track": None}


@respx.mock
def test_currently_playing_maps_track():
    oauth.set_tokens(
        TokenSet(access_token="access-abc", refresh_token="refresh-xyz", expires_at=None)
    )
    respx.get("https://api.spotify.com/v1/me/player/currently-playing").mock(
        return_value=Response(
            200,
            json={
                "is_playing": True,
                "item": {
                    "id": "track1",
                    "name": "Now Song",
                    "artists": [{"name": "Artist A"}, {"name": "Artist B"}],
                    "album": {
                        "name": "Album",
                        "images": [{"url": "https://i.scdn.co/image/album"}],
                    },
                    "external_urls": {
                        "spotify": "https://open.spotify.com/track/track1"
                    },
                },
            },
        )
    )
    response = client.get("/spotify/currently-playing")
    assert response.status_code == 200
    assert response.json() == {
        "is_playing": True,
        "track": {
            "track_id": "track1",
            "name": "Now Song",
            "artists": ["Artist A", "Artist B"],
            "album": "Album",
            "spotify_url": "https://open.spotify.com/track/track1",
            "image_url": "https://i.scdn.co/image/album",
        },
    }


@respx.mock
def test_currently_playing_paused_hides_track():
    oauth.set_tokens(
        TokenSet(access_token="access-abc", refresh_token="refresh-xyz", expires_at=None)
    )
    respx.get("https://api.spotify.com/v1/me/player/currently-playing").mock(
        return_value=Response(
            200,
            json={
                "is_playing": False,
                "item": {
                    "id": "track1",
                    "name": "Paused Song",
                    "artists": [{"name": "Artist A"}],
                    "album": {
                        "name": "Album",
                        "images": [{"url": "https://i.scdn.co/image/album"}],
                    },
                    "external_urls": {
                        "spotify": "https://open.spotify.com/track/track1"
                    },
                },
            },
        )
    )
    response = client.get("/spotify/currently-playing")
    assert response.status_code == 200
    assert response.json() == {"is_playing": False, "track": None}


@respx.mock
def test_currently_playing_episode_without_album():
    oauth.set_tokens(
        TokenSet(access_token="access-abc", refresh_token="refresh-xyz", expires_at=None)
    )
    respx.get("https://api.spotify.com/v1/me/player/currently-playing").mock(
        return_value=Response(
            200,
            json={
                "is_playing": True,
                "item": {
                    "id": "episode1",
                    "name": "Podcast Episode",
                    "artists": [{"name": "Host"}],
                    "external_urls": {
                        "spotify": "https://open.spotify.com/episode/episode1"
                    },
                },
            },
        )
    )
    response = client.get("/spotify/currently-playing")
    assert response.status_code == 200
    assert response.json() == {"is_playing": False, "track": None}


@respx.mock
def test_parallel_refresh_single_flight(monkeypatch):
    monkeypatch.setattr(
        "app.spotify.oauth.settings.spotify_client_id",
        "test-client-id",
    )
    monkeypatch.setattr(
        "app.spotify.oauth.settings.spotify_client_secret",
        "test-secret",
    )
    oauth.set_tokens(
        TokenSet(access_token="old-access", refresh_token="refresh-xyz", expires_at=None)
    )

    def me_handler(request):
        auth = request.headers.get("Authorization", "")
        if auth == "Bearer old-access":
            return Response(401, json={"error": {"message": "expired"}})
        return Response(
            200,
            json={
                "id": "user123",
                "display_name": "Test User",
                "images": [],
                "country": "US",
                "product": "premium",
            },
        )

    respx.get("https://api.spotify.com/v1/me").mock(side_effect=me_handler)
    refresh_route = respx.post("https://accounts.spotify.com/api/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "new-access",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )
    )

    async def fetch_parallel():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            return await asyncio.gather(*[ac.get("/spotify/me") for _ in range(5)])

    responses = asyncio.run(fetch_parallel())
    assert all(response.status_code == 200 for response in responses)
    assert refresh_route.call_count == 1
    assert oauth.get_tokens().access_token == "new-access"


@respx.mock
def test_top_tracks_maps_items():
    oauth.set_tokens(
        TokenSet(access_token="access-abc", refresh_token="refresh-xyz", expires_at=None)
    )
    respx.get("https://api.spotify.com/v1/me/top/tracks").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": "track1",
                        "name": "Top Song",
                        "artists": [{"name": "Artist"}],
                        "album": {
                            "name": "Album",
                            "images": [{"url": "https://i.scdn.co/image/top"}],
                        },
                        "external_urls": {
                            "spotify": "https://open.spotify.com/track/track1"
                        },
                    }
                ]
            },
        )
    )
    response = client.get("/spotify/top/tracks?limit=10&time_range=medium_term")
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "track_id": "track1",
                "name": "Top Song",
                "artists": ["Artist"],
                "album": "Album",
                "spotify_url": "https://open.spotify.com/track/track1",
                "image_url": "https://i.scdn.co/image/top",
            }
        ]
    }


@respx.mock
def test_top_artists_maps_items():
    oauth.set_tokens(
        TokenSet(access_token="access-abc", refresh_token="refresh-xyz", expires_at=None)
    )
    respx.get("https://api.spotify.com/v1/me/top/artists").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": "artist1",
                        "name": "Top Artist",
                        "genres": ["pop", "rock"],
                        "images": [{"url": "https://i.scdn.co/image/artist"}],
                        "external_urls": {
                            "spotify": "https://open.spotify.com/artist/artist1"
                        },
                    }
                ]
            },
        )
    )
    response = client.get("/spotify/top/artists?limit=10&time_range=medium_term")
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "artist_id": "artist1",
                "name": "Top Artist",
                "genres": ["pop", "rock"],
                "image_url": "https://i.scdn.co/image/artist",
                "spotify_url": "https://open.spotify.com/artist/artist1",
            }
        ]
    }
