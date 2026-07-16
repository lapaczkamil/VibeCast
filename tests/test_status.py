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
    assert settings.spotify_client_id in (None, "")
    assert settings.spotify_client_secret in (None, "")
    assert settings.openai_api_key in (None, "")
    assert settings.spotify_redirect_uri == "http://127.0.0.1:8000/callback"
