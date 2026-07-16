from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


client = TestClient(app)


def test_status_returns_ok():
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == settings.app_name
    assert "spotify" not in body
    assert "openai" not in body
    assert "api_key" not in str(body).lower()
    assert "secret" not in str(body).lower()


def test_settings_defaults_are_optional():
    assert isinstance(settings.app_name, str)
    assert settings.app_name

    assert settings.spotify_client_id is None or isinstance(
        settings.spotify_client_id, str
    )
    assert settings.spotify_client_secret is None or isinstance(
        settings.spotify_client_secret, str
    )
    assert settings.openai_api_key is None or isinstance(settings.openai_api_key, str)

    assert isinstance(settings.spotify_redirect_uri, str)
    default_redirect_uri = "http://127.0.0.1:8000/callback"
    if settings.spotify_redirect_uri != default_redirect_uri:
        assert settings.spotify_redirect_uri.startswith("http")
        assert "callback" in settings.spotify_redirect_uri
