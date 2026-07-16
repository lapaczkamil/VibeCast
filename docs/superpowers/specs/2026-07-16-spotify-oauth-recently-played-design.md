# VibeCast — Spotify OAuth & recently played

**Date:** 2026-07-16  
**Status:** Approved for planning

## Product context

VibeCast is an AI-driven app that recommends movies based on the mood of the user's music. This spec covers the **first backend slice**: authenticate with Spotify and expose recently played tracks as JSON. Mood analysis and movie recommendations are out of scope here.

## Goal

Enable a single local user to log in via Spotify Authorization Code flow and fetch recently played tracks through FastAPI endpoints (usable from Swagger `/docs`).

## Scope

In scope:
- Refactor into a small `app/` package (keep `/status`)
- Spotify OAuth Authorization Code flow with `httpx`
- In-memory token store (single-user, lost on process restart)
- Minimal access-token refresh using stored `refresh_token` when Spotify returns 401
- `GET /spotify/recently-played` returning a normalized JSON list
- Env: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`
- Scope: `user-read-recently-played`

Out of scope:
- AI / mood inference / movie recommendations
- HTML UI
- Database or multi-user sessions
- Other Spotify endpoints (top tracks, playlists, currently playing)
- OpenAI integration

## Architecture

| Module | Responsibility |
|--------|----------------|
| `app/main.py` | FastAPI app, routers, `GET /status` |
| `app/config.py` | `Settings` via pydantic-settings |
| `app/spotify/oauth.py` | Authorize URL, code exchange, in-memory tokens, refresh |
| `app/spotify/client.py` | Call Spotify Web API (`/me/player/recently-played`) |
| `app/spotify/routes.py` | HTTP routes for auth + recently played |
| `app/spotify/schemas.py` | Response models for recently played items |

Compatibility: keep a thin root entry so `uvicorn` can run the app (e.g. `app.main:app` or a small `main.py` re-export). Prefer `uvicorn app.main:app`.

### Token store

One in-process slot holding at least:
- `access_token`
- `refresh_token` (if provided)
- `expires_at` (optional, if returned)

No cookies. Restart requires re-login.

## OAuth flow

1. User opens `GET /auth/spotify/login` → `302` to Spotify Authorize.
2. Spotify redirects to **`http://127.0.0.1:8000/callback`** (matches Developer Dashboard).
3. `GET /callback` exchanges `code` for tokens, stores them in memory, returns JSON `{ "authenticated": true }`.
4. User calls `GET /spotify/recently-played` with the stored access token.

PKCE is optional for this local confidential client (client secret present). Use standard Authorization Code with client id + secret.

### State parameter

Include a random `state` on login; validate on callback. Store pending state in memory until callback (or reject mismatch).

## API

### `GET /status`

Unchanged: `{ "status": "ok", "service": "<APP_NAME>" }`.

### `GET /auth/spotify/login`

Redirects to Spotify. Requires client id/secret/redirect URI configured; otherwise `503`.

### `GET /callback`

Query: `code`, `state` (and Spotify `error` if denied).

Success: `{ "authenticated": true }`  
Failure: `400` (bad/missing code or state) or appropriate error; never log or return tokens.

### `GET /auth/spotify/status`

`{ "authenticated": true | false }` — no token values.

### `GET /spotify/recently-played?limit=20`

- Default `limit=20`, clamp to Spotify max (50).
- `401` if no access token.
- On Spotify `401`, attempt one refresh then retry once; if still failing, clear tokens and return `401`.
- Spotify upstream errors (other): `502` with a short safe message.

Response:

```json
{
  "items": [
    {
      "played_at": "2026-07-16T12:00:00.000Z",
      "track_id": "string",
      "name": "string",
      "artists": ["string"],
      "album": "string",
      "spotify_url": "https://open.spotify.com/track/..."
    }
  ]
}
```

Map from Spotify's `items[].played_at` and `items[].track` fields. Skip items missing a track object.

## Environment

| Variable | Required for Spotify features | Default / example |
|----------|-------------------------------|-------------------|
| `SPOTIFY_CLIENT_ID` | Yes | (from Dashboard) |
| `SPOTIFY_CLIENT_SECRET` | Yes | (from Dashboard) |
| `SPOTIFY_REDIRECT_URI` | Yes | `http://127.0.0.1:8000/callback` |
| `APP_NAME` | No | `VibeCast` |
| `OPENAI_API_KEY` | No | unused in this slice |

Update `.env.example` accordingly. Developer Dashboard Redirect URI must equal `SPOTIFY_REDIRECT_URI`.

## Security

- Never return access/refresh tokens in API responses or logs.
- Validate OAuth `state`.
- `.env` remains gitignored.

## Testing

- Unit/integration tests with mocked Spotify HTTP (httpx mock or respx): login redirect URL shape, callback token store, recently-played mapping, 401 without token, refresh-then-retry path.
- No live Spotify calls in CI/tests.

## Success criteria

1. With valid Dashboard credentials and Redirect URI `http://127.0.0.1:8000/callback`, login + callback stores tokens.
2. `/spotify/recently-played` returns normalized items after login.
3. `/auth/spotify/status` reflects authentication without leaking secrets.
4. `/status` still works.
5. Tests pass without real Spotify credentials.

## Run (after implementation)

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Open `/docs`, hit login (or browse `/auth/spotify/login`), then call recently-played.
