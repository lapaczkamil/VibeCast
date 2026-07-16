import respx
from httpx import Response
from fastapi.testclient import TestClient

from app.main import app
from app.spotify import oauth


client = TestClient(app)


def setup_function() -> None:
    oauth.clear_tokens()
    oauth.clear_pending_state()


def test_auth_status_false_when_logged_out():
    response = client.get("/auth/spotify/status")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_login_redirects_to_spotify_when_configured(monkeypatch):
    monkeypatch.setattr(
        "app.spotify.routes.settings.spotify_client_id",
        "test-client-id",
    )
    monkeypatch.setattr(
        "app.spotify.routes.settings.spotify_client_secret",
        "test-secret",
    )
    monkeypatch.setattr(
        "app.spotify.routes.settings.spotify_redirect_uri",
        "http://127.0.0.1:8000/callback",
    )
    response = client.get("/auth/spotify/login", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.spotify.com/authorize")
    assert "client_id=test-client-id" in location
    assert "response_type=code" in location
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8000%2Fcallback" in location
    assert "scope=user-read-recently-played" in location
    assert "state=" in location


def test_login_returns_503_when_missing_credentials(monkeypatch):
    monkeypatch.setattr("app.spotify.routes.settings.spotify_client_id", None)
    monkeypatch.setattr("app.spotify.routes.settings.spotify_client_secret", None)
    response = client.get("/auth/spotify/login", follow_redirects=False)
    assert response.status_code == 503


@respx.mock
def test_callback_stores_tokens_and_redirects_to_frontend(monkeypatch):
    monkeypatch.setattr(
        "app.spotify.oauth.settings.spotify_client_id",
        "test-client-id",
    )
    monkeypatch.setattr(
        "app.spotify.oauth.settings.spotify_client_secret",
        "test-secret",
    )
    monkeypatch.setattr(
        "app.spotify.oauth.settings.spotify_redirect_uri",
        "http://127.0.0.1:8000/callback",
    )
    monkeypatch.setattr(
        "app.spotify.routes.settings.frontend_url",
        "http://127.0.0.1:5173",
    )
    state = oauth.create_login_state()
    respx.post("https://accounts.spotify.com/api/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "access-abc",
                "refresh_token": "refresh-xyz",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )
    )
    response = client.get(
        f"/callback?code=auth-code&state={state}",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://127.0.0.1:5173/"
    assert "access-abc" not in response.headers.get("location", "")
    assert client.get("/auth/spotify/status").json() == {"authenticated": True}
    tokens = oauth.get_tokens()
    assert tokens is not None
    assert tokens.access_token == "access-abc"
    assert tokens.refresh_token == "refresh-xyz"


def test_callback_rejects_bad_state_with_frontend_redirect(monkeypatch):
    monkeypatch.setattr(
        "app.spotify.routes.settings.frontend_url",
        "http://127.0.0.1:5173",
    )
    response = client.get(
        "/callback?code=auth-code&state=wrong",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://127.0.0.1:5173/?auth_error=1"


def test_callback_spotify_error_query_redirects(monkeypatch):
    monkeypatch.setattr(
        "app.spotify.routes.settings.frontend_url",
        "http://127.0.0.1:5173",
    )
    response = client.get(
        "/callback?error=access_denied",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://127.0.0.1:5173/?auth_error=1"


@respx.mock
def test_callback_exchange_failure_redirects(monkeypatch):
    monkeypatch.setattr(
        "app.spotify.oauth.settings.spotify_client_id",
        "test-client-id",
    )
    monkeypatch.setattr(
        "app.spotify.oauth.settings.spotify_client_secret",
        "test-secret",
    )
    monkeypatch.setattr(
        "app.spotify.oauth.settings.spotify_redirect_uri",
        "http://127.0.0.1:8000/callback",
    )
    monkeypatch.setattr(
        "app.spotify.routes.settings.frontend_url",
        "http://127.0.0.1:5173",
    )
    state = oauth.create_login_state()
    respx.post("https://accounts.spotify.com/api/token").mock(
        return_value=Response(500, json={"error": "server_error"})
    )
    response = client.get(
        f"/callback?code=auth-code&state={state}",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://127.0.0.1:5173/?auth_error=1"
    assert oauth.get_tokens() is None
