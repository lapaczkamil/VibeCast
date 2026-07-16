# TMDB Movie Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect TMDB via server-side API key and expose movie status + search in FastAPI and the React SPA (with or without Spotify login).

**Architecture:** New `app/movies/` package (client, schemas, routes). SPA calls `/api/movies/*` through existing Vite proxy. No Spotify dependency for movie search.

**Tech Stack:** FastAPI, httpx, respx, pytest, Vite React TypeScript

**Spec:** `docs/superpowers/specs/2026-07-16-tmdb-movies-design.md`

## Global Constraints

- Env: `TMDB_API_KEY` → `Settings.tmdb_api_key`
- TMDB v3 base `https://api.themoviedb.org/3` with query `api_key`
- Poster base `https://image.tmdb.org/t/p/w185`
- Never return or log the API key in responses
- Search requires non-empty `q` (400); missing key → 503; upstream fail → 502
- Status always 200 with `{configured, reachable}`
- Movie search works without Spotify auth
- UI: Movies below Spotify CTA when logged out; after Top artists when logged in
- Use Linux Node on WSL: `PATH="$HOME/.local/node/bin:$PATH"`
- `npm run build` must pass; backend tests mocked (no live TMDB in CI)

## File Structure

| File | Role |
|------|------|
| `app/config.py` | Add `tmdb_api_key` |
| `app/movies/__init__.py` | Package |
| `app/movies/schemas.py` | `MoviesStatus`, `MovieItem`, `MovieSearchResponse` |
| `app/movies/client.py` | `ping_tmdb`, `search_movies`, `map_search` |
| `app/movies/routes.py` | `/movies/status`, `/movies/search` |
| `app/main.py` | Include movies router |
| `.env.example` | `TMDB_API_KEY=` |
| `tests/test_movies.py` | Status + search tests |
| `frontend/src/types.ts` | Movie types |
| `frontend/src/api.ts` | `fetchMoviesStatus`, `searchMovies` |
| `frontend/src/components/MoviesSearch.tsx` | Reusable search UI |
| `frontend/src/App.tsx` | Mount MoviesSearch logged-out + logged-in |
| `frontend/src/styles.css` | Movie result styles |
| `README.md` | TMDB key setup |

---

### Task 1: Backend TMDB module

**Files:**
- Modify: `app/config.py`, `app/main.py`, `.env.example`, local `.env` (not committed)
- Create: `app/movies/*`, `tests/test_movies.py`

**Interfaces:**
- `Settings.tmdb_api_key: str | None = None`
- `def tmdb_configured() -> bool`
- `async def fetch_configuration(api_key: str) -> httpx.Response` → `GET /3/configuration`
- `async def fetch_movie_search(api_key: str, query: str, page: int) -> httpx.Response` → `GET /3/search/movie`
- `def map_search_results(payload: dict, query: str, page: int) -> MovieSearchResponse`
- Routes as in spec

- [ ] **Step 1: Write failing tests**

`tests/test_movies.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect RED**

```bash
source .venv/bin/activate
pytest tests/test_movies.py -v
```

Expected: FAIL (module/routes missing).

- [ ] **Step 3: Implement movies package**

1. Add `tmdb_api_key` to Settings.
2. Implement schemas, client, routes per spec.
3. `app.include_router(movies_router)` in `main.py`.
4. Update `.env.example` + local `.env` with `TMDB_API_KEY=`.

For status ping use `GET https://api.themoviedb.org/3/configuration?api_key=...`.  
For search use `GET https://api.themoviedb.org/3/search/movie?api_key=...&query=...&page=...`.

`year`: if `release_date` length ≥ 4, take `[:4]`, else `None`.  
`poster_url`: if `poster_path`, `f"https://image.tmdb.org/t/p/w185{poster_path}"`, else `None`.

- [ ] **Step 4: Full backend suite**

```bash
pytest -q
```

Expected: all PASS (including existing Spotify tests).

- [ ] **Step 5: Commit**

```bash
git add app/config.py app/main.py app/movies .env.example tests/test_movies.py
git commit -m "feat: add TMDB movies status and search API"
```

---

### Task 2: Frontend Movies search UI

**Files:**
- Modify: `frontend/src/types.ts`, `api.ts`, `App.tsx`, `styles.css`, `README.md`
- Create: `frontend/src/components/MoviesSearch.tsx` (and export via existing components pattern if used)

**Interfaces:**
- Types matching backend search/status
- `searchMovies(q: string, page?: number)`
- Optional `fetchMoviesStatus()` for clearer “not configured” messaging

- [ ] **Step 1: Types + API helpers**

```typescript
export type MovieItem = {
  id: number;
  title: string;
  year: string | null;
  overview: string;
  poster_url: string | null;
};

export type MovieSearchResponse = {
  query: string;
  page: number;
  total_results: number;
  items: MovieItem[];
};
```

Implement `searchMovies` → `GET /api/movies/search?q=...`. On !ok, throw with status-aware message (503 → TMDB not configured).

- [ ] **Step 2: MoviesSearch component**

Controlled query input, Search button (and submit on Enter), results list with poster/title/year/overview truncate. States: idle, loading, empty, error.

- [ ] **Step 3: Wire into App**

- Logged-out: render `<MoviesSearch />` below Spotify CTA (not inside hero brand block).
- Logged-in: after Top artists section, heading “Movies” + `<MoviesSearch />`.

- [ ] **Step 4: Styles**

Movie rows consistent with track list; poster thumb ~w185 scaled down; no card-grid dashboard clutter; keep listening-room palette.

- [ ] **Step 5: README**

Document TMDB key URL + `TMDB_API_KEY` in `.env`.

- [ ] **Step 6: Verify**

```bash
export PATH="$HOME/.local/node/bin:$PATH"
cd frontend && npm run build
cd .. && source .venv/bin/activate && pytest -q
```

Expected: build OK; all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src README.md
git commit -m "feat: add TMDB movie search section to SPA"
```

---

## Self-Review

1. **Spec coverage:** Config, status, search, SPA both views, security, tests, README — Tasks 1–2.
2. **Placeholders:** None.
3. **Consistency:** Poster URL prefix, field names, `/movies/*` paths, no Spotify gate on movies.
