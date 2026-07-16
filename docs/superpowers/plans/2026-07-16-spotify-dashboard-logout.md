# Spotify Dashboard Data + Logout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand Spotify OAuth scopes, add me / currently-playing / top tracks / top artists APIs plus logout, and update the React SPA to a scrolling listening dashboard with Log out.

**Architecture:** Keep in-memory tokens. Factor a shared authenticated Spotify GET helper with refresh-on-401. Frontend loads sections in parallel after auth; logout clears server tokens and local UI state.

**Tech Stack:** FastAPI, httpx, respx, pytest, Vite React TypeScript

**Spec:** `docs/superpowers/specs/2026-07-16-spotify-dashboard-logout-design.md`

## Global Constraints

- OAuth scope string exactly: `user-read-recently-played user-read-private user-read-currently-playing user-top-read`
- Never return access/refresh tokens
- Spotify data routes: no token → 401; 401 from Spotify → one refresh + retry; then clear + 401; other errors → 502
- Currently-playing Spotify 204 / empty → `{ "is_playing": false, "track": null }` (not 502)
- Top defaults: `limit=10`, `time_range=medium_term`; clamp limit 1–50
- Logout: `POST /auth/spotify/logout` → `{ "authenticated": false }`, idempotent
- UI: header brand + profile + Log out; sections Now playing → Recently played → Top tracks → Top artists
- Section failures isolated; `npm run build` must pass; use Linux Node (`$HOME/.local/node/bin` on PATH) in WSL

## File Structure

| File | Change |
|------|--------|
| `app/spotify/oauth.py` | Expand `SCOPE` |
| `app/spotify/schemas.py` | Me, CurrentlyPlaying, TopTrack, TopArtist models |
| `app/spotify/client.py` | Fetch + map helpers for new endpoints |
| `app/spotify/routes.py` | `_spotify_get`, logout, me, currently-playing, tops; refactor recently-played to use helper |
| `tests/test_spotify_oauth.py` | Scope assertion + logout tests |
| `tests/test_spotify_dashboard.py` | New endpoint tests |
| `frontend/src/types.ts` | New types |
| `frontend/src/api.ts` | New fetchers + logout |
| `frontend/src/App.tsx` | Dashboard UI |
| `frontend/src/styles.css` | Header profile + section styles |
| `README.md` | Note re-login for new scopes |

---

### Task 1: Backend scopes, logout, Spotify data endpoints

**Files:**
- Modify: `app/spotify/oauth.py`, `schemas.py`, `client.py`, `routes.py`
- Modify: `tests/test_spotify_oauth.py`
- Create: `tests/test_spotify_dashboard.py`

**Interfaces:**
- `SCOPE = "user-read-recently-played user-read-private user-read-currently-playing user-top-read"`
- Schemas: `SpotifyProfile`, `PlayingTrack`, `CurrentlyPlayingResponse`, `TopTrackItem`, `TopTracksResponse`, `TopArtistItem`, `TopArtistsResponse`
- Client: `fetch_me`, `map_me`, `fetch_currently_playing`, `map_currently_playing`, `fetch_top_tracks`, `map_top_tracks`, `fetch_top_artists`, `map_top_artists` (plus existing recently-played)
- Routes helper: `async def _spotify_request(method_fetch) -> httpx.Response` implementing auth/refresh/clear/502
- `POST /auth/spotify/logout`
- `GET /spotify/me`, `/spotify/currently-playing`, `/spotify/top/tracks`, `/spotify/top/artists`

- [ ] **Step 1: Update scope test + write logout + dashboard failing tests**

In `tests/test_spotify_oauth.py`, change scope assertion to:

```python
assert "scope=user-read-recently-played+user-read-private+user-read-currently-playing+user-top-read" in location
# OR check each scope segment is present if URL encoding differs:
for part in (
    "user-read-recently-played",
    "user-read-private",
    "user-read-currently-playing",
    "user-top-read",
):
    assert part in location
```

Prefer checking each part is in `location` (robust to `+` vs `%20`).

Add:

```python
def test_logout_clears_tokens():
    oauth.set_tokens(
        oauth.TokenSet(access_token="a", refresh_token="r", expires_at=None)
    )
    response = client.post("/auth/spotify/logout")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False}
    assert oauth.get_tokens() is None
    assert client.get("/auth/spotify/status").json() == {"authenticated": False}


def test_logout_idempotent_when_logged_out():
    response = client.post("/auth/spotify/logout")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False}
```

Create `tests/test_spotify_dashboard.py` with respx mocks covering:
- `test_me_unauthorized_without_token` → 401
- `test_me_maps_profile` → mocked GET `https://api.spotify.com/v1/me`
- `test_currently_playing_empty_204` → 204 → `{is_playing: false, track: null}`
- `test_currently_playing_maps_track` → 200 with item
- `test_top_tracks_maps_items` → GET `.../me/top/tracks`
- `test_top_artists_maps_items` → GET `.../me/top/artists`

Use `oauth.set_tokens(TokenSet(...))` in setup for authenticated cases; `setup_function` clears tokens.

- [ ] **Step 2: Run tests — expect RED**

```bash
source .venv/bin/activate
pytest tests/test_spotify_oauth.py tests/test_spotify_dashboard.py -v
```

Expected: FAIL (missing routes / wrong scope).

- [ ] **Step 3: Implement backend**

1. Update `SCOPE` in `oauth.py`.
2. Add schemas per spec JSON shapes.
3. Extend `client.py` with URLs:
   - `https://api.spotify.com/v1/me`
   - `https://api.spotify.com/v1/me/player/currently-playing`
   - `https://api.spotify.com/v1/me/top/tracks`
   - `https://api.spotify.com/v1/me/top/artists`
4. In `routes.py`:
   - `POST /auth/spotify/logout` → `oauth.clear_tokens(); return {"authenticated": False}`
   - Extract helper used by all Spotify GETs including recently-played:

```python
async def _authed_spotify(fetch) -> httpx.Response:
    tokens = oauth.get_tokens()
    if tokens is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    response = await fetch(tokens.access_token)
    if response.status_code == 401 and tokens.refresh_token:
        try:
            new_tokens = await oauth.refresh_access_token()
            oauth.set_tokens(new_tokens)
            response = await fetch(new_tokens.access_token)
        except Exception:
            oauth.clear_tokens()
            raise HTTPException(status_code=401, detail="Not authenticated") from None
    if response.status_code == 401:
        oauth.clear_tokens()
        raise HTTPException(status_code=401, detail="Not authenticated")
    return response
```

For currently-playing: if status in `(204, 200)` with empty body → return empty response model; if 200 with JSON → map; if other non-success after auth handling → 502. Specifically: after `_authed_spotify`, if `status_code == 204` or (`status_code == 200` and not response.content) → empty; elif `status_code == 200` → map; else → 502.

For other endpoints: require 200 else 502, then map.

Validate `time_range` in `{"short_term", "medium_term", "long_term"}` else 400.

- [ ] **Step 4: Run full backend suite**

```bash
pytest -v
```

Expected: all PASS (including existing recently-played).

- [ ] **Step 5: Commit**

```bash
git add app/spotify tests/test_spotify_oauth.py tests/test_spotify_dashboard.py
git commit -m "feat: add Spotify me, now playing, tops, and logout API"
```

---

### Task 2: Frontend dashboard UI + logout

**Files:**
- Modify: `frontend/src/types.ts`, `api.ts`, `App.tsx`, `styles.css`
- Modify: `README.md`

**Interfaces:**
- Types matching backend schemas
- `fetchMe`, `fetchCurrentlyPlaying`, `fetchTopTracks`, `fetchTopArtists`, `logoutSpotify` (POST)
- Logged-in UI per spec

- [ ] **Step 1: Extend types and api**

Add types from spec. Add API functions using `/api/...` paths. `logoutSpotify`:

```typescript
export async function logoutSpotify(): Promise<AuthStatus> {
  const res = await fetch("/api/auth/spotify/logout", { method: "POST" });
  if (!res.ok) throw new Error("Failed to log out");
  return res.json();
}
```

- [ ] **Step 2: Implement logged-in dashboard in App.tsx**

Pattern:
1. Load auth status first.
2. If authenticated, `Promise.allSettled` for me, currently-playing, recently-played, top tracks, top artists (limit 10, medium_term).
3. Per-section state: `{ status: 'loading'|'ok'|'error', data?, error? }` or separate useState per section.
4. Header: brand, avatar (`image_url` or initials), `display_name`, Log out button calling `logoutSpotify` then reset to logged-out.
5. Sections in order with titles: Now playing, Recently played, Top tracks, Top artists.
6. Keep logged-out landing unchanged.

Extract small presentational components in the same file or `frontend/src/components/*.tsx` if `App.tsx` exceeds ~250 lines — prefer split `ProfileHeader`, `NowPlaying`, `TrackList` (reuse), `ArtistList`.

- [ ] **Step 3: Styles**

Extend listening-room CSS: header row with profile cluster, avatar circle, section spacing, now-playing block. No purple/cream+terracotta clichés. Avoid card-grid dashboard look.

- [ ] **Step 4: README**

Add: after this update, Log out then Log in again so Spotify grants new scopes.

- [ ] **Step 5: Build + backend tests**

```bash
export PATH="$HOME/.local/node/bin:$PATH"
cd frontend && npm run build
cd .. && source .venv/bin/activate && pytest -q
```

Expected: build exit 0; all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src frontend/README.md README.md 2>/dev/null || git add frontend/src README.md
git commit -m "feat: show Spotify profile, now playing, tops, and logout in SPA"
```

Do not commit `node_modules` or `dist`.

---

## Self-Review

1. **Spec coverage:** Scopes, logout, four data endpoints, refresh helper, SPA sections, parallel load, build gate — Tasks 1–2.
2. **Placeholders:** None.
3. **Consistency:** Scope string, response field names, `/api` paths, medium_term defaults aligned.
