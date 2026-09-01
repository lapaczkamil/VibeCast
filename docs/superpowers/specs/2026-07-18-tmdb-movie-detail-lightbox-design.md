# TMDB movie detail for lightbox — Design

## Goal

When the user opens the recommendation poster lightbox, load **fresh English TMDB movie details** so the panel shows a clearer picture of what the film is about (overview + tagline + genres + runtime), instead of relying only on the short Chroma-ingest blurb.

## Decisions

| Topic | Choice |
|-------|--------|
| Source | Live `GET /movie/{id}` via backend (EN: `language=en-US`) |
| When | On lightbox open (lazy), not in `POST /recommend` |
| Language | English only |
| Cursor on poster | `pointer` (no zoom-in / magnifier) |
| Soft-fail | Keep Chroma `overview` from recommend payload as fallback |

## Out of scope

- Polish (`pl-PL`) or language toggle
- LLM rewrite of plot
- Prefetching details for all recommend items
- Re-ingesting Chroma with richer fields
- Keywords / credits / videos appends

## Backend

### Endpoint

`GET /movies/{tmdb_id}` → `MovieDetailResponse`

```json
{
  "tmdb_id": 550,
  "title": "Fight Club",
  "year": "1999",
  "overview": "...",
  "tagline": "...",
  "genres": ["Drama"],
  "runtime": 139,
  "poster_url": "https://image.tmdb.org/t/p/w780/..."
}
```

- `runtime`: minutes (`int | null` if missing)
- `tagline` / `overview`: empty string when absent
- `genres`: ordered name list from TMDB `genres` array
- `year`: from `release_date` (first 4 chars) or `null`
- `poster_url`: prefer `w780` (or existing poster helper); `null` if no path

Reuse `fetch_movie` in `app/movies/client.py`, pass `language=en-US`. Map JSON in client (or small mapper next to search mappers).

### Errors

| Condition | Status |
|-----------|--------|
| TMDB key missing | 503 |
| TMDB network/HTTP failure | 502 |
| TMDB 404 | 404 |
| Invalid `tmdb_id` (non-positive) | 422 |

## Frontend

### Data flow

1. User clicks current poster → lightbox opens immediately with title / year / rating from recommend item, poster, and loading state for detail body.
2. `GET /movies/{tmdb_id}` (session-memory cache per id so reopen is instant).
3. On success: show tagline (if non-empty), genres, runtime, and TMDB overview.
4. On failure: show Chroma `overview` from recommend item (if any) and a short muted note that live details were unavailable; never leave the lightbox empty if Chroma text exists.

### UI

- Layout unchanged in spirit: poster + body (meta, title, scrollable text).
- Meta row: year, rating (from recommend), genres (comma or middot separated), runtime as `Nh Nm` or `Nm` when present.
- Tagline: italic / muted line under title when present.
- Poster hotspot: `cursor: pointer`; aria-label stays “View overview…”.

### States

- `loading`: skeleton or short “Loading details…” in overview area
- `ready`: full detail fields
- `error`: fallback overview + soft message

## Testing

- Backend: map fixture TMDB movie JSON → schema; route happy path + 404/503.
- Frontend: no required E2E; manual — open lightbox, see genres/tagline/overview; cursor is pointer.

## Compatibility

- Recommend payload may still include Chroma `overview` for fallback and for any non-lightbox UI.
- Existing `/movies/search` and `/movies/status` unchanged.
