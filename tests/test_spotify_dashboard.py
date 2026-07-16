import respx
from httpx import Response
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
                        "album": {"name": "Album"},
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
