# VibeCast — Spotify profile, now playing, tops + logout

**Date:** 2026-07-16  
**Status:** Approved for planning

## Product context

VibeCast matches movies to music mood. This slice expands the logged-in Spotify surface: show richer listening context and let the user log out. Movie/AI recommendations remain out of scope.

## Goal

Extend FastAPI + React SPA so an authenticated user can see profile, currently playing, recently played, top tracks, and top artists, and can clear the server-side Spotify session via Log out.

## Scope

In scope:
- Expand OAuth scopes and require re-login after deploy
- Backend endpoints: `/spotify/me`, `/spotify/currently-playing`, `/spotify/top/tracks`, `/spotify/top/artists`
- `POST /auth/spotify/logout` clears in-memory tokens
- Shared authenticated Spotify request helper (401 → refresh once → retry / clear)
- Frontend logged-in scroll page: header (brand, profile, logout) → now playing → recently played → top tracks → top artists
- Per-section loading/error/empty; one section failure must not blank the whole page
- Tests with mocked Spotify HTTP; update login scope assertions

Out of scope:
- Movie/AI UI
- Changing Spotify Redirect URI
- Cookies / multi-user DB sessions
- Top time-range picker UI (fixed `medium_term` for this slice)
- Currently-playing auto-poll / websockets (fetch once on load; optional manual refresh later)

## OAuth scopes

Space-separated authorize `scope`:

```
user-read-recently-played user-read-private user-read-currently-playing user-top-read
```

Users with an old token must **log out and log in again** to grant new scopes.

## Architecture

Reuse `app/spotify/` package:

| Piece | Role |
|-------|------|
| `oauth.py` | Expanded `SCOPE`; `clear_tokens` used by logout |
| `client.py` | Fetch helpers for me / currently-playing / top tracks / top artists |
| `schemas.py` | Response models |
| `routes.py` | New routes + logout; factor shared `_spotify_get` with refresh |

Frontend:

| Piece | Role |
|-------|------|
| `api.ts` | New fetch helpers + `logoutSpotify()` |
| `types.ts` | Matching types |
| `App.tsx` (and small section components if needed) | Logged-in layout |

## API

Auth rules for Spotify data routes: no token → `401`; Spotify `401` → refresh once then retry; still failing → clear tokens + `401`; other upstream errors → `502` (short safe message). Never return tokens.

### `POST /auth/spotify/logout`

Clears in-memory tokens. Response: `{ "authenticated": false }`. Idempotent if already logged out.

### `GET /spotify/me`

```json
{
  "id": "string",
  "display_name": "string",
  "image_url": "string | null",
  "country": "string | null",
  "product": "string | null"
}
```

Map from Spotify `/v1/me` (`images[0].url` when present).

### `GET /spotify/currently-playing`

When nothing playing / 204 from Spotify:

```json
{ "is_playing": false, "track": null }
```

When playing:

```json
{
  "is_playing": true,
  "track": {
    "track_id": "string",
    "name": "string",
    "artists": ["string"],
    "album": "string",
    "spotify_url": "string",
    "image_url": "string | null"
  }
}
```

Source: `/v1/me/player/currently-playing`. Treat missing body / 204 as not playing (not 502).

### `GET /spotify/top/tracks?limit=10&time_range=medium_term`

Clamp `limit` 1–50. Default `time_range=medium_term` (allow `short_term` / `long_term` in API for future, UI uses medium).

```json
{
  "items": [
    {
      "track_id": "string",
      "name": "string",
      "artists": ["string"],
      "album": "string",
      "spotify_url": "string"
    }
  ]
}
```

### `GET /spotify/top/artists?limit=10&time_range=medium_term`

```json
{
  "items": [
    {
      "artist_id": "string",
      "name": "string",
      "genres": ["string"],
      "image_url": "string | null",
      "spotify_url": "string"
    }
  ]
}
```

### Existing

`GET /spotify/recently-played`, login/callback/status unchanged except scope string on authorize URL.

## UI

**Logged out:** unchanged (brand + CTA).

**Logged in header:** VibeCast (strong) · avatar + display_name · Log out button (text CTA, not floating badge clutter).

**Body (one scroll):**
1. Now playing  
2. Recently played  
3. Top tracks  
4. Top artists  

Preserve listening-room visual language from the current SPA. No dashboard stat strips; no movie placeholders.

Data load: after auth status true, fetch sections in parallel (`Promise.allSettled` or equivalent). Show section-level errors with retry.

Logout: call `POST /api/auth/spotify/logout`, clear local state, show logged-out landing.

## Testing

- Backend: logout clears tokens; me / currently-playing / tops mapping; 401 without token; currently-playing empty/204; login URL contains new scopes.
- Frontend: `npm run build` must pass.

## Success criteria

1. After re-login with new scopes, SPA shows profile, now playing (or empty), recent, tops.
2. Log out returns to logged-out UI and `/auth/spotify/status` is false.
3. Existing recently-played still works.
4. Backend tests pass; frontend build succeeds.

## Run note

After deploying this slice: open SPA → Log out (if connected) → Log in with Spotify again to approve new scopes.
