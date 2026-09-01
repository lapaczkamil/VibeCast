# TMDB Movie Detail Lightbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On lightbox open, fetch live English TMDB movie details (overview, tagline, genres, runtime) via `GET /movies/{tmdb_id}`, with Chroma overview fallback and pointer cursor on the poster.

**Architecture:** Extend `app/movies/` with `MovieDetailResponse`, `map_movie_detail`, and `language=en-US` on `fetch_movie`. SPA lightbox loads details lazily with an in-memory cache; recommend Chroma `overview` remains fallback only.

**Tech Stack:** FastAPI, httpx, respx, pytest, React TypeScript, Vite

**Spec:** `docs/superpowers/specs/2026-07-18-tmdb-movie-detail-lightbox-design.md`

## Global Constraints

- TMDB language: `en-US` only
- Lazy fetch on lightbox open (not in `POST /recommend`)
- Soft-fail: Chroma `overview` from recommend item as fallback
- Poster hotspot cursor: `pointer` (no `zoom-in`)
- Never return or log the API key
- Route must not break `/movies/status` or `/movies/search` (register path param after static paths)
- Use Linux Node on WSL: `PATH="$HOME/.local/node/bin:$PATH"`
- Backend tests mocked with respx (no live TMDB in CI)

## File Structure

| File | Role |
|------|------|
| `app/movies/schemas.py` | Add `MovieDetailResponse` |
| `app/movies/client.py` | `language=en-US` on `fetch_movie`; `map_movie_detail` |
| `app/movies/routes.py` | `GET /movies/{tmdb_id}` |
| `tests/test_movies.py` | Detail mapper + route tests |
| `frontend/src/types.ts` | `MovieDetail` type |
| `frontend/src/api.ts` | `fetchMovieDetail` + module cache |
| `frontend/src/components/MovieOverviewLightbox.tsx` | Load detail, show tagline/genres/runtime, fallback |
| `frontend/src/styles.css` | Tagline/genres/loading styles; `cursor: pointer` |

---

### Task 1: Backend movie detail endpoint

**Files:**
- Modify: `app/movies/schemas.py`
- Modify: `app/movies/client.py`
- Modify: `app/movies/routes.py`
- Modify: `tests/test_movies.py`

**Interfaces:**
- Consumes: existing `fetch_movie`, `_map_year`, `_map_poster_url`, `tmdb_configured`, `settings.tmdb_api_key`
- Produces:
  - `class MovieDetailResponse(BaseModel)` with fields: `tmdb_id: int`, `title: str`, `year: str | None`, `overview: str`, `tagline: str`, `genres: list[str]`, `runtime: int | None`, `poster_url: str | None`
  - `async def fetch_movie(api_key: str, movie_id: int) -> httpx.Response` — params include `language=en-US`
  - `def map_movie_detail(payload: dict) -> MovieDetailResponse`
  - Route `GET /movies/{tmdb_id}` → `MovieDetailResponse`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_movies.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_movies.py::test_map_movie_detail tests/test_movies.py::test_movie_detail_happy_path -v`

Expected: FAIL (import/attribute errors for `map_movie_detail` / missing route)

- [ ] **Step 3: Implement schema, mapper, fetch language, route**

`app/movies/schemas.py` — add:

```python
class MovieDetailResponse(BaseModel):
    tmdb_id: int
    title: str
    year: str | None
    overview: str
    tagline: str
    genres: list[str]
    runtime: int | None
    poster_url: str | None
```

`app/movies/client.py` — update `fetch_movie`:

```python
async def fetch_movie(api_key: str, movie_id: int) -> httpx.Response:
    async with httpx.AsyncClient(timeout=TMDB_TIMEOUT) as client:
        return await client.get(
            f"{TMDB_BASE_URL}/movie/{movie_id}",
            params={"api_key": api_key, "language": "en-US"},
        )
```

Add mapper (poster size `w780`):

```python
def map_movie_detail(payload: dict) -> MovieDetailResponse:
    genres = [
        str(genre["name"])
        for genre in payload.get("genres") or []
        if isinstance(genre, dict) and genre.get("name")
    ]
    runtime = payload.get("runtime")
    runtime_minutes: int | None
    if runtime is None or runtime == "" or runtime == 0:
        runtime_minutes = None
    else:
        try:
            runtime_minutes = int(runtime)
        except (TypeError, ValueError):
            runtime_minutes = None
        if runtime_minutes is not None and runtime_minutes <= 0:
            runtime_minutes = None

    return MovieDetailResponse(
        tmdb_id=int(payload["id"]),
        title=str(payload.get("title") or "Unknown"),
        year=_map_year(payload.get("release_date")),
        overview=(payload.get("overview") or "").strip(),
        tagline=(payload.get("tagline") or "").strip(),
        genres=genres,
        runtime=runtime_minutes,
        poster_url=_map_poster_url(payload.get("poster_path"), size="w780"),
    )
```

Import `MovieDetailResponse` at top of `client.py`.

`app/movies/routes.py` — add imports and route **after** `/movies/search` (static paths first):

```python
from fastapi import APIRouter, HTTPException, Path, Query

from app.movies.client import (
    fetch_configuration,
    fetch_movie,
    fetch_movie_search,
    map_movie_detail,
    map_search_results,
    tmdb_configured,
)
from app.movies.schemas import MovieDetailResponse, MovieSearchResponse, MoviesStatus


@router.get("/movies/{tmdb_id}", response_model=MovieDetailResponse)
async def movie_detail(
    tmdb_id: int = Path(gt=0),
) -> MovieDetailResponse:
    if not tmdb_configured(settings.tmdb_api_key):
        raise HTTPException(status_code=503, detail="TMDB API key not configured")
    try:
        response = await fetch_movie(settings.tmdb_api_key, tmdb_id)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="TMDB API request failed")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Movie not found")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="TMDB API request failed")
    return map_movie_detail(response.json())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_movies.py -q`

Expected: all PASS (existing search/status + new detail tests)

- [ ] **Step 5: Commit**

```bash
git add app/movies/schemas.py app/movies/client.py app/movies/routes.py tests/test_movies.py
git commit -m "feat: add GET /movies/{tmdb_id} TMDB detail endpoint"
```

---

### Task 2: Frontend lightbox uses live TMDB detail

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/components/MovieOverviewLightbox.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `GET /api/movies/{tmdb_id}` → `MovieDetail`
- Produces:
  - `type MovieDetail = { tmdb_id: number; title: string; year: string | null; overview: string; tagline: string; genres: string[]; runtime: number | null; poster_url: string | null }`
  - `fetchMovieDetail(tmdbId: number): Promise<MovieDetail>` with module-level `Map` cache
  - Lightbox shows loading / ready / error+fallback; cursor `pointer`

- [ ] **Step 1: Add types and API helper**

In `frontend/src/types.ts`:

```typescript
export type MovieDetail = {
  tmdb_id: number;
  title: string;
  year: string | null;
  overview: string;
  tagline: string;
  genres: string[];
  runtime: number | null;
  poster_url: string | null;
};
```

In `frontend/src/api.ts` (import `MovieDetail`; place near other movie helpers):

```typescript
const movieDetailCache = new Map<number, MovieDetail>();

export async function fetchMovieDetail(tmdbId: number): Promise<MovieDetail> {
  const cached = movieDetailCache.get(tmdbId);
  if (cached) return cached;

  const res = await fetch(`/api/movies/${tmdbId}`);
  if (!res.ok) {
    if (res.status === 503) {
      throw new Error(
        await errorMessageFromResponse(res, "TMDB API key not configured"),
      );
    }
    if (res.status === 404) {
      throw new Error(await errorMessageFromResponse(res, "Movie not found"));
    }
    if (res.status === 502) {
      throw new Error(
        await errorMessageFromResponse(res, "TMDB API request failed"),
      );
    }
    throw new Error(
      await errorMessageFromResponse(res, "Failed to load movie details"),
    );
  }
  const detail = (await res.json()) as MovieDetail;
  movieDetailCache.set(tmdbId, detail);
  return detail;
}
```

- [ ] **Step 2: Update lightbox to fetch and render detail**

Replace body of `MovieOverviewLightbox` so it:

1. Keeps Escape / body scroll / portal / poster from recommend item (or detail poster if recommend poster empty — optional; prefer recommend `poster_url` for visual continuity).
2. On mount / `movie.tmdb_id` change: `setStatus("loading")`, call `fetchMovieDetail`, then `ready` or `error`.
3. Meta: year (prefer detail.year ?? movie.year), rating from recommend, genres joined with ` · `, runtime formatted.
4. Tagline under title when non-empty.
5. Overview: detail.overview when ready; on error use `movie.overview` + muted “Live details unavailable.”; while loading show “Loading details…”.

Helper for runtime (in the component file or small local function):

```typescript
function formatRuntime(minutes: number | null | undefined): string | null {
  if (minutes == null || minutes <= 0) return null;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h <= 0) return `${m}m`;
  if (m <= 0) return `${h}h`;
  return `${h}h ${m}m`;
}
```

Sketch of state + effect:

```tsx
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { fetchMovieDetail } from "../api";
import type { MovieDetail, RecommendMovieItem } from "../types";

type DetailStatus = "loading" | "ready" | "error";

// inside component:
const [status, setStatus] = useState<DetailStatus>("loading");
const [detail, setDetail] = useState<MovieDetail | null>(null);

useEffect(() => {
  let cancelled = false;
  setStatus("loading");
  setDetail(null);
  void fetchMovieDetail(movie.tmdb_id)
    .then((value) => {
      if (cancelled) return;
      setDetail(value);
      setStatus("ready");
    })
    .catch(() => {
      if (cancelled) return;
      setDetail(null);
      setStatus("error");
    });
  return () => {
    cancelled = true;
  };
}, [movie.tmdb_id]);
```

Render overview region:

```tsx
{status === "loading" ? (
  <p className="movie-lightbox-overview movie-lightbox-overview--muted">
    Loading details…
  </p>
) : null}
{status === "ready" && detail ? (
  <>
    {detail.tagline ? (
      <p className="movie-lightbox-tagline">{detail.tagline}</p>
    ) : null}
    <div className="movie-lightbox-overview-scroll">
      {detail.overview ? (
        <p className="movie-lightbox-overview">{detail.overview}</p>
      ) : (
        <p className="movie-lightbox-overview movie-lightbox-overview--empty">
          No overview.
        </p>
      )}
    </div>
  </>
) : null}
{status === "error" ? (
  <div className="movie-lightbox-overview-scroll">
    <p className="movie-lightbox-overview movie-lightbox-overview--muted">
      Live details unavailable.
    </p>
    {(movie.overview?.trim() ?? "") ? (
      <p className="movie-lightbox-overview">{movie.overview}</p>
    ) : (
      <p className="movie-lightbox-overview movie-lightbox-overview--empty">
        No overview.
      </p>
    )}
  </div>
) : null}
```

Meta genres/runtime only when `status === "ready" && detail`.

Place tagline **under** the title (title stays from `movie.title` for stability, or use `detail.title` when ready — prefer `movie.title`).

- [ ] **Step 3: Styles + cursor**

In `frontend/src/styles.css`:

1. Change `.stage-poster-hotspot` from `cursor: zoom-in` to `cursor: pointer`.
2. Add:

```css
.movie-lightbox-tagline {
  margin: 0;
  font-size: 0.95rem;
  font-style: italic;
  line-height: 1.4;
  color: var(--ink-muted);
}

.movie-lightbox-overview--muted {
  color: var(--ink-muted);
  font-size: 0.9rem;
}

.movie-lightbox-genres {
  margin: 0;
}
```

- [ ] **Step 4: Verify build**

Run:

```bash
cd frontend && export PATH="$HOME/.local/node/bin:$PATH" && npm run build
```

Expected: `tsc -b && vite build` succeeds.

Also re-run: `.venv/bin/pytest tests/test_movies.py -q` → PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts \
  frontend/src/components/MovieOverviewLightbox.tsx frontend/src/styles.css
git commit -m "feat: load TMDB detail in movie overview lightbox"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| `GET /movies/{tmdb_id}` EN detail | Task 1 |
| Fields: overview, tagline, genres, runtime, poster w780 | Task 1 |
| Errors 503/502/404/422 | Task 1 |
| Lazy fetch on open + cache | Task 2 |
| Fallback Chroma overview | Task 2 |
| Tagline / genres / runtime UI | Task 2 |
| Cursor pointer | Task 2 |
| Out of scope (PL, LLM, prefetch) | Not implemented |
