import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.main import app
from app.spotify import oauth
from app.spotify.oauth import TokenSet

client = TestClient(app)
TOKENS = TokenSet(access_token="access-abc", refresh_token="refresh-xyz", expires_at=None)


def setup_function():
    oauth.clear_tokens()
    oauth.clear_pending_state()


def test_search_unauthorized():
    r = client.get("/spotify/search", params={"q": "radiohead"})
    assert r.status_code == 401


@respx.mock
def test_search_happy_path():
    oauth.set_tokens(TOKENS)
    respx.get("https://api.spotify.com/v1/search").mock(
        return_value=Response(
            200,
            json={
                "tracks": {
                    "items": [
                        {
                            "id": "abc",
                            "name": "Creep",
                            "artists": [{"name": "Radiohead"}],
                            "album": {
                                "name": "Pablo Honey",
                                "images": [{"url": "https://img/x"}],
                            },
                            "external_urls": {"spotify": "https://open.spotify.com/track/abc"},
                        }
                    ]
                }
            },
        )
    )
    r = client.get("/spotify/search", params={"q": "creep", "limit": 10})
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["id"] == "abc"
    assert item["name"] == "Creep"
    assert item["artists"] == ["Radiohead"]


def test_search_blank_query_422():
    oauth.set_tokens(TOKENS)
    r = client.get("/spotify/search", params={"q": "  "})
    assert r.status_code == 422
