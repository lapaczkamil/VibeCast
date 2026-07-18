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
                        "vote_average": 8.369,
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
    assert body["items"][0]["poster_url"] == "https://image.tmdb.org/t/p/w342/poster.jpg"
    assert body["items"][0]["rating"] == 8.4
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


from app.movies.client import map_movie_detail


FIGHT_CLUB_TMDB = {
    "id": 550,
    "title": "Fight Club",
    "release_date": "1999-10-15",
    "overview": "A ticking-time-bomb of a man...",
    "tagline": "Mischief. Mayhem. Soap.",
    "genres": [{"id": 18, "name": "Drama"}],
    "runtime": 139,
    "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
}


def test_map_movie_detail():
    detail = map_movie_detail(FIGHT_CLUB_TMDB)
    assert detail.tmdb_id == 550
    assert detail.title == "Fight Club"
    assert detail.year == "1999"
    assert detail.overview.startswith("A ticking")
    assert detail.tagline == "Mischief. Mayhem. Soap."
    assert detail.genres == ["Drama"]
    assert detail.runtime == 139
    assert detail.poster_url == (
        "https://image.tmdb.org/t/p/w780/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg"
    )


def test_map_movie_detail_missing_optional_fields():
    detail = map_movie_detail({"id": 1, "title": "Bare"})
    assert detail.year is None
    assert detail.overview == ""
    assert detail.tagline == ""
    assert detail.genres == []
    assert detail.runtime is None
    assert detail.poster_url is None


def test_movie_detail_requires_key(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", None)
    response = client.get("/movies/550")
    assert response.status_code == 503


def test_movie_detail_rejects_non_positive_id(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    assert client.get("/movies/0").status_code == 422
    assert client.get("/movies/-1").status_code == 422


@respx.mock
def test_movie_detail_happy_path(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    route = respx.get("https://api.themoviedb.org/3/movie/550").mock(
        return_value=Response(200, json=FIGHT_CLUB_TMDB)
    )
    response = client.get("/movies/550")
    assert response.status_code == 200
    body = response.json()
    assert body["tmdb_id"] == 550
    assert body["genres"] == ["Drama"]
    assert body["runtime"] == 139
    assert body["tagline"] == "Mischief. Mayhem. Soap."
    assert "test-key" not in str(body)
    assert route.calls[0].request.url.params["language"] == "en-US"
    assert route.calls[0].request.url.params["api_key"] == "test-key"


@respx.mock
def test_movie_detail_not_found(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    respx.get("https://api.themoviedb.org/3/movie/999999").mock(
        return_value=Response(404, json={"status_message": "Not found"})
    )
    response = client.get("/movies/999999")
    assert response.status_code == 404


@respx.mock
def test_movie_detail_upstream_fail(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    respx.get("https://api.themoviedb.org/3/movie/550").mock(
        return_value=Response(500, json={"status_message": "Error"})
    )
    response = client.get("/movies/550")
    assert response.status_code == 502


@respx.mock
def test_movie_detail_transport_error(monkeypatch):
    monkeypatch.setattr(movies_routes.settings, "tmdb_api_key", "test-key")
    respx.get("https://api.themoviedb.org/3/movie/550").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    response = client.get("/movies/550")
    assert response.status_code == 502
