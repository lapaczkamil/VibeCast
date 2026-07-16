# React Frontend (Login + Recently Played) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Vite React TypeScript SPA for Spotify login and recently played, wired to FastAPI via `/api` proxy, with OAuth callback redirecting to the SPA.

**Architecture:** Keep in-memory Spotify tokens on FastAPI. SPA never stores tokens. Vite proxies `/api` → `:8000` (strip `/api` prefix). Successful `/callback` redirects to `FRONTEND_URL`.

**Tech Stack:** Vite, React 19 (or current Vite React template), TypeScript, CSS (no UI kit), FastAPI, pytest

**Spec:** `docs/superpowers/specs/2026-07-16-react-frontend-design.md`

## Global Constraints

- Spotify Redirect URI stays `http://127.0.0.1:8000/callback`
- Default `FRONTEND_URL` / `frontend_url` = `http://127.0.0.1:5173`
- Proxy: `/api/auth/spotify/status` → backend `/auth/spotify/status`
- SPA must not hold Spotify access/refresh tokens
- Logged-out UI: brand VibeCast + one subtitle + one Spotify login CTA
- Logged-in UI: brand header + recently played list (name, artists, album, played_at, Spotify link)
- Visual: listening-room atmosphere; avoid purple-on-white and cream+terracotta; expressive display font + readable body font; 2–3 intentional motions
- No movie/AI UI in this slice
- Backend tests must pass; `npm run build` must succeed

## File Structure

| File | Responsibility |
|------|----------------|
| `app/config.py` | Add `frontend_url` |
| `app/spotify/routes.py` | Callback → redirect to frontend (success + auth errors) |
| `.env.example` / local `.env` | `FRONTEND_URL` |
| `tests/test_spotify_oauth.py` | Expect 302 to frontend URL on success; error → redirect with `auth_error` |
| `frontend/` | Vite React TS app |
| `frontend/vite.config.ts` | Dev server + `/api` proxy |
| `frontend/src/api.ts` | `fetchAuthStatus`, `fetchRecentlyPlayed` |
| `frontend/src/types.ts` | Shared types |
| `frontend/src/App.tsx` | Logged-out / logged-in UI |
| `frontend/src/styles.css` | Theme, layout, motion |
| `frontend/src/main.tsx` | Entry |
| `.gitignore` | `frontend/node_modules`, `frontend/dist` |
| `README.md` | Two-terminal run instructions |

---

### Task 1: Backend callback redirect to frontend

**Files:**
- Modify: `app/config.py`
- Modify: `app/spotify/routes.py`
- Modify: `.env.example`
- Modify: local `.env` (do not commit)
- Modify: `tests/test_spotify_oauth.py`

**Interfaces:**
- Consumes: existing OAuth helpers
- Produces:
  - `Settings.frontend_url: str = "http://127.0.0.1:5173"`
  - Successful callback: `302` Location = `settings.frontend_url` (normalize to include trailing behavior: use `str(settings.frontend_url).rstrip("/") + "/"`)
  - Error callback (`error` query, bad state, exchange failure): `302` to `frontend_url + "/?auth_error=1"` (not JSON 400)

- [ ] **Step 1: Update failing/changed tests first**

Replace `test_callback_stores_tokens_and_authenticates` assertions for response status/body with redirect checks, and update error tests:

```python
@respx.mock
def test_callback_stores_tokens_and_redirects_to_frontend(monkeypatch):
    monkeypatch.setattr(
        "app.spotify.oauth.settings.spotify_client_id",
        "test-client-id",
    )
    monkeypatch.setattr(
        "app.spotify.oauth.settings.spotify_client_secret",
        "test-secret",
    )
    monkeypatch.setattr(
        "app.spotify.oauth.settings.spotify_redirect_uri",
        "http://127.0.0.1:8000/callback",
    )
    monkeypatch.setattr(
        "app.spotify.routes.settings.frontend_url",
        "http://127.0.0.1:5173",
    )
    state = oauth.create_login_state()
    respx.post("https://accounts.spotify.com/api/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "access-abc",
                "refresh_token": "refresh-xyz",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )
    )
    response = client.get(
        f"/callback?code=auth-code&state={state}",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://127.0.0.1:5173/"
    assert "access-abc" not in response.headers.get("location", "")
    assert client.get("/auth/spotify/status").json() == {"authenticated": True}
    tokens = oauth.get_tokens()
    assert tokens is not None
    assert tokens.access_token == "access-abc"
    assert tokens.refresh_token == "refresh-xyz"


def test_callback_rejects_bad_state_with_frontend_redirect(monkeypatch):
    monkeypatch.setattr(
        "app.spotify.routes.settings.frontend_url",
        "http://127.0.0.1:5173",
    )
    response = client.get(
        "/callback?code=auth-code&state=wrong",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://127.0.0.1:5173/?auth_error=1"
```

Rename/remove the old `test_callback_rejects_bad_state` and old success test name accordingly. Keep other OAuth tests.

- [ ] **Step 2: Run tests — expect RED**

```bash
source .venv/bin/activate
pytest tests/test_spotify_oauth.py -v
```

Expected: FAIL on status code / JSON assertions (still returns 200 JSON / 400).

- [ ] **Step 3: Implement config + routes**

Add to `Settings` in `app/config.py`:

```python
frontend_url: str = "http://127.0.0.1:5173"
```

In `app/spotify/routes.py`, add helper:

```python
def _frontend_redirect(path_query: str = "/") -> RedirectResponse:
    base = settings.frontend_url.rstrip("/")
    if not path_query.startswith("/"):
        path_query = "/" + path_query
    return RedirectResponse(url=f"{base}{path_query}", status_code=302)
```

Update `spotify_callback`:
- On `error`: return `_frontend_redirect("/?auth_error=1")`
- On bad code/state: same
- On exchange exception: same
- On success after `set_tokens`: return `_frontend_redirect("/")`

`.env.example` add:

```env
FRONTEND_URL=http://127.0.0.1:5173
```

Update local `.env` the same (gitignored).

- [ ] **Step 4: Run full backend suite**

```bash
pytest -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/config.py app/spotify/routes.py .env.example tests/test_spotify_oauth.py
git commit -m "feat: redirect Spotify OAuth callback to frontend URL"
```

---

### Task 2: Vite React SPA (proxy, UI, README)

**Files:**
- Create: entire `frontend/` app via Vite template, then replace/add sources listed below
- Modify: `.gitignore`
- Modify: `README.md`

**Interfaces:**
- Consumes: backend endpoints via `/api/...`
- Produces SPA that:
  - On load: `GET /api/auth/spotify/status`
  - If authenticated: `GET /api/spotify/recently-played?limit=20`
  - Login CTA: `window.location.assign("/api/auth/spotify/login")`
  - Reads `auth_error` query and shows a short error message

- [ ] **Step 1: Scaffold Vite app**

```bash
cd /home/kamil/Projects/VibeCast
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

If `npm create` prompts, use non-interactive flags as above.

- [ ] **Step 2: Configure proxy and gitignore**

`frontend/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
```

Append to root `.gitignore`:

```gitignore
frontend/node_modules/
frontend/dist/
```

- [ ] **Step 3: Add types + API helpers**

`frontend/src/types.ts`:

```typescript
export type AuthStatus = {
  authenticated: boolean;
};

export type RecentlyPlayedItem = {
  played_at: string;
  track_id: string;
  name: string;
  artists: string[];
  album: string;
  spotify_url: string;
};

export type RecentlyPlayedResponse = {
  items: RecentlyPlayedItem[];
};
```

`frontend/src/api.ts`:

```typescript
import type { AuthStatus, RecentlyPlayedResponse } from "./types";

export async function fetchAuthStatus(): Promise<AuthStatus> {
  const res = await fetch("/api/auth/spotify/status");
  if (!res.ok) {
    throw new Error("Failed to load auth status");
  }
  return res.json();
}

export async function fetchRecentlyPlayed(
  limit = 20,
): Promise<RecentlyPlayedResponse> {
  const res = await fetch(`/api/spotify/recently-played?limit=${limit}`);
  if (!res.ok) {
    throw new Error("Failed to load recently played");
  }
  return res.json();
}

export function startSpotifyLogin(): void {
  window.location.assign("/api/auth/spotify/login");
}
```

- [ ] **Step 4: Implement App UI + styles**

Replace `frontend/src/App.tsx` with a single-page flow:
- Parse `auth_error` from `window.location.search`
- `useEffect` load auth status; if true, load recently played
- Logged out: hero with `VibeCast`, subtitle e.g. `Movies matched to the mood of your music.`, button `Log in with Spotify`
- Logged in: header brand + “Connected” text + list of tracks (link opens `spotify_url` in new tab)
- Loading / error+retry / empty states

`frontend/src/styles.css` (and import from `main.tsx`):
- CSS variables: deep charcoal/ink background, warm amber or teal accent (not purple, not cream+terracotta)
- Google fonts via `index.html` link: display e.g. **Fraunces** or **Syne**, body **Source Sans 3** or **DM Sans**
- Full-viewport atmospheric gradient/noise
- Motions: fade-in brand, subtle CTA hover/translate, list stagger fade-in (keep to 2–3)

Remove default Vite `App.css` / logo assets if unused. Keep `main.tsx` mounting `<App />`.

- [ ] **Step 5: Verify build**

```bash
cd frontend
npm run build
```

Expected: exit 0, `dist/` created (gitignored).

- [ ] **Step 6: Update README**

Document:
1. Backend: `uvicorn app.main:app --reload`
2. Frontend: `cd frontend && npm install && npm run dev`
3. Open `http://127.0.0.1:5173/`
4. `FRONTEND_URL` and Spotify Redirect URI notes

- [ ] **Step 7: Re-run backend tests (sanity)**

```bash
cd /home/kamil/Projects/VibeCast
source .venv/bin/activate
pytest -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend .gitignore README.md
git commit -m "feat: add React SPA for Spotify login and recently played"
```

Do not commit `node_modules` or `dist`.

---

## Self-Review

1. **Spec coverage:** Proxy SPA, login CTA, recently played UI, callback redirect, `FRONTEND_URL`, README, OAuth test updates, build gate — Tasks 1–2.
2. **Placeholders:** None.
3. **Consistency:** `/api` strip prefix, redirect to `http://127.0.0.1:5173/`, error `?auth_error=1` aligned across backend tests and SPA.
