# VibeCast — TMDB movie search connection

**Date:** 2026-07-16  
**Status:** Approved for planning

## Product context

VibeCast recommends movies from music mood. This slice connects **TMDB** and exposes search so the product can show real movie data before mood/AI recommendations.

## Goal

Add a TMDB-backed movies module (API key in `.env`) with status + search endpoints and a Movies search section in the React SPA (works with or without Spotify login).

## Scope

In scope:
- `TMDB_API_KEY` in Settings / `.env` / `.env.example`
- Package `app/movies/` (config use via shared Settings, client, schemas, routes)
- `GET /movies/status` — configured + optional reachability ping; never expose API key
- `GET /movies/search?q=&page=1` — normalized movie list
- SPA Movies search UI on logged-out and logged-in views
- Mocked httpx/respx tests; README note for obtaining a TMDB key

Out of scope:
- Mood → movie recommendations / OpenAI
- TMDB auth via user accounts
- Local movie database / caching layer
- Movie detail page beyond search results
- Requiring Spotify login for movie search

## Architecture

```
SPA /api/movies/*  →  FastAPI app/movies  →  TMDB API v3
```

| Module | Role |
|--------|------|
| `app/config.py` | `tmdb_api_key: str | None = None` |
| `app/movies/client.py` | httpx calls to TMDB |
| `app/movies/schemas.py` | Status + search response models |
| `app/movies/routes.py` | HTTP routes |
| `app/main.py` | Include movies router |

TMDB base: `https://api.themoviedb.org/3`  
Auth: query param `api_key` (v3).  
Poster URLs: prefix `https://image.tmdb.org/t/p/w185` + `poster_path` when present.

## API

### `GET /movies/status`

```json
{
  "configured": true,
  "reachable": true
}
```

- `configured`: non-empty `TMDB_API_KEY`
- If not configured: `{ "configured": false, "reachable": false }` (200)
- If configured: lightweight call e.g. `GET /3/configuration` or `/3/movie/popular?page=1`; success → `reachable: true`; failure → `reachable: false` (still 200 — status is diagnostic, not an error page)
- Never return the API key

### `GET /movies/search?q={query}&page=1`

- Require non-empty trimmed `q` else `400`
- Missing/empty API key → `503` `{ "detail": "TMDB API key not configured" }`
- TMDB upstream failure → `502` short safe message
- Clamp `page` to ≥ 1

Response:

```json
{
  "query": "string",
  "page": 1,
  "total_results": 0,
  "items": [
    {
      "id": 123,
      "title": "string",
      "year": "2024",
      "overview": "string",
      "poster_url": "https://image.tmdb.org/t/p/w185/..."
    }
  ]
}
```

- `year` from `release_date` first 4 chars, or `null` / `""` if missing — prefer `string | null`
- `poster_url` null when no `poster_path`
- `overview` may be empty string
- Map from TMDB `/search/movie`

## UI

**Logged out:** Below Spotify CTA, a Movies block: search input + Search button + results list. Does not overpower the VibeCast hero.

**Logged in:** After Top artists, section **Movies** with the same search + results.

Results row: poster (or placeholder), title, year, truncated overview.

States: idle hint, loading, empty results, error (including “TMDB not configured”).

Preserve listening-room visual language. No recommendation/mood copy claiming AI picks yet.

## Security

- API key only server-side
- Do not log full API key
- Status/search responses never include the key

## Testing

- Status when unconfigured / configured+reachable (mocked) / configured+unreachable
- Search 400 empty q, 503 no key, 200 mapping, 502 upstream
- Frontend: `npm run build`

## Success criteria

1. With `TMDB_API_KEY` set, search returns real/mapped results via API and SPA.
2. Without key, status shows not configured; search returns 503; SPA shows clear error.
3. Movie search works without Spotify login.
4. Backend tests pass; frontend build succeeds.

## Run note

Create a free TMDB API key at https://www.themoviedb.org/settings/api and set `TMDB_API_KEY` in `.env`.
