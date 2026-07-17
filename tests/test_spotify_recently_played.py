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


def test_recently_played_unauthorized_without_token():
    response = client.get("/spotify/recently-played")
    assert response.status_code == 401


@respx.mock
def test_recently_played_maps_items():
    oauth.set_tokens(
        TokenSet(access_token="access-abc", refresh_token="refresh-xyz", expires_at=None)
    )
    respx.get("https://api.spotify.com/v1/me/player/recently-played").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "played_at": "2026-07-16T12:00:00.000Z",
                        "track": {
                            "id": "track1",
                            "name": "Song",
                            "artists": [{"name": "Artist"}],
                            "album": {
                                "name": "Album",
                                "images": [{"url": "https://i.scdn.co/image/recent"}],
                            },
                            "external_urls": {
                                "spotify": "https://open.spotify.com/track/track1"
                            },
                        },
                    },
                    {"played_at": "2026-07-16T11:00:00.000Z", "track": None},
                ]
            },
        )
    )
    response = client.get("/spotify/recently-played?limit=20")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "items": [
            {
                "played_at": "2026-07-16T12:00:00.000Z",
                "track_id": "track1",
                "name": "Song",
                "artists": ["Artist"],
                "album": "Album",
                "spotify_url": "https://open.spotify.com/track/track1",
                "image_url": "https://i.scdn.co/image/recent",
            }
        ]
    }
    assert "access-abc" not in str(body)


@respx.mock
def test_recently_played_refreshes_on_401_then_succeeds(monkeypatch):
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
    route = respx.get("https://api.spotify.com/v1/me/player/recently-played")
    route.side_effect = [
        Response(401, json={"error": {"message": "expired"}}),
        Response(
            200,
            json={
                "items": [
                    {
                        "played_at": "2026-07-16T12:00:00.000Z",
                        "track": {
                            "id": "track1",
                            "name": "Song",
                            "artists": [{"name": "Artist"}],
                            "album": {"name": "Album"},
                            "external_urls": {
                                "spotify": "https://open.spotify.com/track/track1"
                            },
                        },
                    }
                ]
            },
        ),
    ]
    respx.post("https://accounts.spotify.com/api/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "new-access",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )
    )
    response = client.get("/spotify/recently-played")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert oauth.get_tokens().access_token == "new-access"
