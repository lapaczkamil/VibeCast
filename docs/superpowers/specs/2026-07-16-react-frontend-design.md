# VibeCast — React frontend (login + recently played)

**Date:** 2026-07-16  
**Status:** Approved for planning

## Product context

VibeCast recommends movies from music mood. This slice adds a React UI for Spotify login and viewing recently played tracks. Mood/AI/movies remain out of scope.

## Goal

Ship a Vite + React + TypeScript SPA that lets a local user log in with Spotify and see their recently played tracks, talking to the existing FastAPI backend via a dev proxy.

## Scope

In scope:
- `frontend/` Vite React TS app
- Logged-out landing: brand + short subtitle + Spotify login CTA
- Logged-in view: brand header + recently played list (name, artists, album, played_at, Spotify link)
- Loading / error / empty states
- Vite proxy: `/api` → `http://127.0.0.1:8000`
- Backend: after successful OAuth callback, redirect to `FRONTEND_URL` instead of returning only JSON
- `FRONTEND_URL` in Settings / `.env` / `.env.example` (default `http://127.0.0.1:5173`)
- README updates for running frontend + backend
- Update OAuth tests for redirect behavior

Out of scope:
- Movie recommendations / AI / mood UI
- Production static hosting / Docker
- Cookie sessions / multi-user auth changes
- Changing Spotify Redirect URI (stays `http://127.0.0.1:8000/callback`)
- Mobile native apps

## Architecture

```
Browser :5173 (Vite)
  /api/*  --proxy-->  FastAPI :8000
```

Auth remains server-side in-memory tokens on FastAPI. The SPA never holds Spotify tokens.

### Login flow

1. User clicks login → full navigation to `/api/auth/spotify/login` (proxied to backend).
2. Spotify authorizes → `GET http://127.0.0.1:8000/callback` (unchanged Dashboard URI).
3. Backend stores tokens → `302` to `{FRONTEND_URL}/` (e.g. `http://127.0.0.1:5173/`).
4. SPA calls `GET /api/auth/spotify/status` then, if authenticated, `GET /api/spotify/recently-played`.

### API usage (from SPA)

| Call | Purpose |
|------|---------|
| `GET /api/auth/spotify/status` | `{ authenticated: boolean }` |
| `GET /api/spotify/recently-played?limit=20` | Track list |
| Navigate to `/api/auth/spotify/login` | Start OAuth (not fetch) |

## UI

One composition (not a dashboard).

**Logged out**
- Brand name **VibeCast** as the dominant text signal
- One short supporting line (music mood → films)
- One CTA: log in with Spotify
- Atmospheric background (listening-room feel); avoid purple-on-white and cream+terracotta clichés
- Expressive display font + readable body font
- Light motion on enter / CTA (2–3 intentional motions max)

**Logged in**
- Brand in header (still strong, not nav-only crumb)
- Connected indicator (text, not floating badge clutter)
- Recently played list as primary content: title, artists, album, played_at, external Spotify link
- States: loading, error with retry, empty list message

No hero cards, no stat strips, no movie placeholders in this slice.

## Backend changes

- Add `frontend_url: str = "http://127.0.0.1:5173"` to Settings (`FRONTEND_URL`).
- `GET /callback` success: `RedirectResponse` to `settings.frontend_url` (trailing path `/` OK).
- On OAuth error paths, prefer redirect to `frontend_url` with a simple query `?auth_error=1` **or** keep JSON 400 for API clients — choose redirect-with-query for browser UX consistency in this slice.
- Existing JSON auth status and recently-played endpoints unchanged (used via proxy).

## Frontend structure

```
frontend/
  package.json
  vite.config.ts      # proxy /api -> :8000, rewrite strip /api prefix OR forward path
  index.html
  src/
    main.tsx
    App.tsx
    api.ts            # status + recently-played helpers
    types.ts
    styles.css        # CSS variables, layout
    components/       # optional small splits if needed
```

Proxy mapping: request `/api/auth/spotify/status` → backend `/auth/spotify/status` (strip `/api` prefix).

## Testing

- Backend: update callback success test to expect `302` Location = frontend URL; keep token store assertions.
- Frontend: minimal Vitest optional; at least typecheck/`npm run build` must succeed. Prefer a small Vitest test for a pure mapper/helper if introduced; otherwise build is the gate for this slice.

## Success criteria

1. With backend + `npm run dev`, user can complete Spotify login and land on the SPA.
2. SPA shows recently played items after login.
3. Logged-out state shows brand + CTA only for the primary action.
4. Spotify Dashboard Redirect URI remains `http://127.0.0.1:8000/callback`.
5. Backend tests pass; frontend production build succeeds.

## Run (after implementation)

```bash
# terminal 1
source .venv/bin/activate
uvicorn app.main:app --reload

# terminal 2
cd frontend && npm install && npm run dev
```

Open `http://127.0.0.1:5173/`.
