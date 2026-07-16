import httpx
import respx
from httpx import Response
from fastapi.testclient import TestClient

from app.main import app
from app.movies import routes as movies_routes


client = TestClient(app)


def test_movies_status_unconfigured(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", None)
    response = client.get("/movies/status")
    assert response.status_code == 200
    assert response.json() == {"configured": False, "reachable": False}
    assert "api_key" not in str(response.json()).lower()
    assert "tmdb" not in str(response.json()).lower() or "configured" in response.json()


@respx.mock
def test_movies_status_configured_reachable(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    respx.get("https://api.themoviedb.org/3/configuration").mock(
        return_value=Response(200, json={"images": {}})
    )
    response = client.get("/movies/status")
    assert response.status_code == 200
    assert response.json() == {"configured": True, "reachable": True}


@respx.mock
def test_movies_status_configured_unreachable(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    respx.get("https://api.themoviedb.org/3/configuration").mock(
        return_value=Response(401, json={"status_message": "Invalid"})
    )
    response = client.get("/movies/status")
    assert response.status_code == 200
    assert response.json() == {"configured": True, "reachable": False}


@respx.mock
def test_movies_status_configured_transport_error(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    respx.get("https://api.themoviedb.org/3/configuration").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    response = client.get("/movies/status")
    assert response.status_code == 200
    assert response.json() == {"configured": True, "reachable": False}


def test_movies_search_requires_query(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    assert client.get("/movies/search").status_code == 400
    assert client.get("/movies/search?q=%20").status_code == 400


def test_movies_search_requires_key(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", None)
    response = client.get("/movies/search?q=inception")
    assert response.status_code == 503


@respx.mock
def test_movies_search_maps_results(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    respx.get("https://api.themoviedb.org/3/search/movie").mock(
        return_value=Response(
            200,
            json={
                "page": 1,
                "total_results": 1,
                "results": [
                    {
                        "id": 27205,
                        "title": "Inception",
                        "release_date": "2010-07-16",
                        "overview": "A thief...",
                        "poster_path": "/poster.jpg",
                    }
                ],
            },
        )
    )
    response = client.get("/movies/search?q=inception")
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "inception"
    assert body["items"][0]["id"] == 27205
    assert body["items"][0]["year"] == "2010"
    assert body["items"][0]["poster_url"] == "https://image.tmdb.org/t/p/w185/poster.jpg"
    assert "test-key" not in str(body)


@respx.mock
def test_movies_search_upstream_error(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    respx.get("https://api.themoviedb.org/3/search/movie").mock(
        return_value=Response(500, json={"status_message": "fail"})
    )
    assert client.get("/movies/search?q=x").status_code == 502


@respx.mock
def test_movies_search_transport_error(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    respx.get("https://api.themoviedb.org/3/search/movie").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    response = client.get("/movies/search?q=x")
    assert response.status_code == 502
    assert response.json() == {"detail": "TMDB API request failed"}
