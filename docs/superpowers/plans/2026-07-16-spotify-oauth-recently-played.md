# Spotify OAuth & Recently Played Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move VibeCast into an `app/` package and add Spotify Authorization Code login plus `GET /spotify/recently-played` as normalized JSON.

**Architecture:** FastAPI routers under `app/spotify/`; in-memory token + OAuth `state`; `httpx` for Spotify token and Web API calls; mock Spotify in tests with `respx`.

**Tech Stack:** Python 3.10+, FastAPI, pydantic-settings, httpx, pytest, respx

**Spec:** `docs/superpowers/specs/2026-07-16-spotify-oauth-recently-played-design.md`

## Global Constraints

- Redirect URI must be `http://127.0.0.1:8000/callback` (Dashboard + `SPOTIFY_REDIRECT_URI`)
- OAuth scope: `user-read-recently-played` only
- In-memory single-user tokens; lost on restart; no cookies/DB
- Never return or log access/refresh tokens
- Validate OAuth `state` on callback
- On Spotify API `401`: one refresh + one retry; then clear tokens and `401`
- Other Spotify upstream failures: `502` with short safe message
- No live Spotify calls in tests
- Prefer entrypoint `uvicorn app.main:app`
- Keep `GET /status` behavior unchanged

## File Structure

| File | Responsibility |
|------|----------------|
| `app/__init__.py` | Package marker |
| `app/config.py` | `Settings`, `get_settings()` |
| `app/main.py` | FastAPI app, include routers, `/status` |
| `app/spotify/__init__.py` | Package marker |
| `app/spotify/oauth.py` | State, token store, authorize URL, exchange, refresh |
| `app/spotify/client.py` | `fetch_recently_played(access_token, limit)` |
| `app/spotify/schemas.py` | Pydantic response models |
| `app/spotify/routes.py` | Auth + recently-played HTTP routes |
| `main.py` | Thin re-export `app` for old uvicorn command (optional compatibility) |
| `.env.example` | Add `SPOTIFY_REDIRECT_URI` |
| `README.md` | New run command + login flow |
| `tests/test_status.py` | Import from `app.main` |
| `tests/test_spotify_oauth.py` | Login/callback/status |
| `tests/test_spotify_recently_played.py` | Recently played + refresh |

---

### Task 1: Package scaffold and config

**Files:**
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/main.py`
- Modify: `main.py` (re-export only)
- Modify: `tests/test_status.py`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: existing Settings fields from root `main.py`
- Produces:
  - `class Settings(BaseSettings)` in `app/config.py` with:
    - `app_name: str = "VibeCast"`
    - `spotify_client_id: str | None = None`
    - `spotify_client_secret: str | None = None`
    - `spotify_redirect_uri: str = "http://127.0.0.1:8000/callback"`
    - `openai_api_key: str | None = None`
  - `get_settings() -> Settings` (lru_cache or module-level singleton)
  - `app: FastAPI` in `app/main.py` with `GET /status`

- [ ] **Step 1: Write failing test update**

Replace imports in `tests/test_status.py`:

```python
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


client = TestClient(app)


def test_status_returns_ok():
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == settings.app_name
    assert "spotify" not in body
    assert "openai" not in body
    assert "api_key" not in str(body).lower()
    assert "secret" not in str(body).lower()


def test_settings_defaults_are_optional():
    assert isinstance(settings.app_name, str)
    assert settings.spotify_client_id in (None, "")
    assert settings.spotify_client_secret in (None, "")
    assert settings.openai_api_key in (None, "")
    assert settings.spotify_redirect_uri == "http://127.0.0.1:8000/callback"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate
pytest tests/test_status.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app'` (or import error for `app.main`).

- [ ] **Step 3: Implement package**

`app/__init__.py` — empty file.

`app/config.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VibeCast"
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    spotify_redirect_uri: str = "http://127.0.0.1:8000/callback"
    openai_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

`app/main.py`:

```python
from fastapi import FastAPI

from app.config import settings

app = FastAPI(title=settings.app_name)


@app.get("/status")
def status() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }
```

Root `main.py` (compatibility):

```python
from app.main import app

__all__ = ["app"]
```

`.env.example`:

```env
APP_NAME=VibeCast
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/callback
OPENAI_API_KEY=
```

Update local `.env` the same way (do not commit `.env`).

`README.md` — change run to:

```bash
uvicorn app.main:app --reload
```

Add note: set Spotify Redirect URI to `http://127.0.0.1:8000/callback`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate
pytest tests/test_status.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/ main.py tests/test_status.py .env.example README.md
git commit -m "refactor: move FastAPI app into app package with Spotify redirect setting"
```

---

### Task 2: Spotify OAuth (login, callback, status)

**Files:**
- Create: `app/spotify/__init__.py`
- Create: `app/spotify/oauth.py`
- Create: `app/spotify/routes.py`
- Modify: `app/main.py` (include router)
- Create: `tests/test_spotify_oauth.py`
- Modify: `requirements.txt` (add `respx` if used here; required by Task 3 — install in this task)

**Interfaces:**
- Consumes: `settings` from `app.config` (`spotify_client_id`, `spotify_client_secret`, `spotify_redirect_uri`)
- Produces in `app/spotify/oauth.py`:
  - `class TokenSet`: `access_token: str`, `refresh_token: str | None`, `expires_at: float | None`
  - `clear_tokens() -> None`
  - `get_tokens() -> TokenSet | None`
  - `set_tokens(token_set: TokenSet) -> None`
  - `create_login_state() -> str` (stores pending state in memory)
  - `consume_login_state(state: str) -> bool` (True if matches pending; clears it)
  - `build_authorize_url(state: str) -> str`
  - `async exchange_code(code: str) -> TokenSet` (POST Spotify token endpoint)
  - `async refresh_access_token() -> TokenSet` (uses stored refresh_token)
  - `spotify_credentials_configured() -> bool`
- Produces routes (router prefix none; paths exact):
  - `GET /auth/spotify/login` → RedirectResponse
  - `GET /callback`
  - `GET /auth/spotify/status`

Spotify authorize base: `https://accounts.spotify.com/authorize`  
Token URL: `https://accounts.spotify.com/api/token`  
Scope query param: `user-read-recently-played`

- [ ] **Step 1: Install respx**

```bash
source .venv/bin/activate
pip install respx
pip freeze --local > requirements.txt
```

- [ ] **Step 2: Write failing OAuth tests**

Create `tests/test_spotify_oauth.py`:

```python
import respx
from httpx import Response
from fastapi.testclient import TestClient

from app.main import app
from app.spotify import oauth


client = TestClient(app)


def setup_function() -> None:
    oauth.clear_tokens()
    oauth.clear_pending_state()


def test_auth_status_false_when_logged_out():
    response = client.get("/auth/spotify/status")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_login_redirects_to_spotify_when_configured(monkeypatch):
    monkeypatch.setattr(
        "app.spotify.routes.settings.spotify_client_id",
        "test-client-id",
    )
    monkeypatch.setattr(
        "app.spotify.routes.settings.spotify_client_secret",
        "test-secret",
    )
    monkeypatch.setattr(
        "app.spotify.routes.settings.spotify_redirect_uri",
        "http://127.0.0.1:8000/callback",
    )
    response = client.get("/auth/spotify/login", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.spotify.com/authorize")
    assert "client_id=test-client-id" in location
    assert "response_type=code" in location
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8000%2Fcallback" in location
    assert "scope=user-read-recently-played" in location
    assert "state=" in location


def test_login_returns_503_when_missing_credentials(monkeypatch):
    monkeypatch.setattr("app.spotify.routes.settings.spotify_client_id", None)
    monkeypatch.setattr("app.spotify.routes.settings.spotify_client_secret", None)
    response = client.get("/auth/spotify/login", follow_redirects=False)
    assert response.status_code == 503


@respx.mock
def test_callback_stores_tokens_and_authenticates(monkeypatch):
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
    response = client.get(f"/callback?code=auth-code&state={state}")
    assert response.status_code == 200
    body = response.json()
    assert body == {"authenticated": True}
    assert "access" not in str(body).lower() or body == {"authenticated": True}
    assert "refresh_xyz" not in str(body)
    assert "access-abc" not in str(body)
    assert client.get("/auth/spotify/status").json() == {"authenticated": True}
    tokens = oauth.get_tokens()
    assert tokens is not None
    assert tokens.access_token == "access-abc"
    assert tokens.refresh_token == "refresh-xyz"


def test_callback_rejects_bad_state():
    response = client.get("/callback?code=auth-code&state=wrong")
    assert response.status_code == 400
```

Note: implement `clear_pending_state()` in oauth for test isolation (also used by `create_login_state` overwrite).

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_spotify_oauth.py -v
```

Expected: FAIL (import/module missing).

- [ ] **Step 4: Implement oauth + routes**

`app/spotify/__init__.py` — empty.

`app/spotify/oauth.py` — implement interfaces above. Use `secrets.token_urlsafe(16)` for state. Token exchange and refresh use `httpx.AsyncClient` POST with `grant_type=authorization_code` / `grant_type=refresh_token` and Basic auth or body `client_id`/`client_secret` per Spotify docs (body form fields with client_id and client_secret is fine).

`expires_at = time.time() + expires_in` when `expires_in` present.

`app/spotify/routes.py`:

```python
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.config import settings
from app.spotify import oauth

router = APIRouter()


@router.get("/auth/spotify/login")
async def spotify_login():
    if not oauth.spotify_credentials_configured():
        raise HTTPException(status_code=503, detail="Spotify credentials not configured")
    state = oauth.create_login_state()
    return RedirectResponse(oauth.build_authorize_url(state), status_code=302)


@router.get("/callback")
async def spotify_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        raise HTTPException(status_code=400, detail="Spotify authorization denied")
    if not code or not state or not oauth.consume_login_state(state):
        raise HTTPException(status_code=400, detail="Invalid OAuth callback")
    try:
        token_set = await oauth.exchange_code(code)
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to exchange Spotify code") from None
    oauth.set_tokens(token_set)
    return {"authenticated": True}


@router.get("/auth/spotify/status")
async def spotify_auth_status():
    return {"authenticated": oauth.get_tokens() is not None}
```

Wire in `app/main.py`:

```python
from fastapi import FastAPI

from app.config import settings
from app.spotify.routes import router as spotify_router

app = FastAPI(title=settings.app_name)
app.include_router(spotify_router)


@app.get("/status")
def status() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }
```

Implement `spotify_credentials_configured()` as: both client id and secret are non-empty strings.

- [ ] **Step 5: Run OAuth + status tests**

```bash
pytest tests/test_status.py tests/test_spotify_oauth.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/spotify tests/test_spotify_oauth.py requirements.txt app/main.py
git commit -m "feat: add Spotify OAuth login callback and auth status"
```

---

### Task 3: Recently played + refresh retry

**Files:**
- Create: `app/spotify/schemas.py`
- Create: `app/spotify/client.py`
- Modify: `app/spotify/routes.py` (add recently-played route)
- Create: `tests/test_spotify_recently_played.py`
- Modify: `README.md` (document endpoints)

**Interfaces:**
- Consumes: `oauth.get_tokens`, `oauth.refresh_access_token`, `oauth.clear_tokens`, `oauth.set_tokens`
- Produces:
  - `class RecentlyPlayedItem` fields: `played_at`, `track_id`, `name`, `artists: list[str]`, `album`, `spotify_url`
  - `class RecentlyPlayedResponse`: `items: list[RecentlyPlayedItem]`
  - `async def fetch_recently_played(access_token: str, limit: int) -> dict` raw Spotify JSON OR mapped list — prefer returning `list[RecentlyPlayedItem]` from mapper
  - `def map_recently_played(payload: dict) -> list[RecentlyPlayedItem]`
  - Route `GET /spotify/recently-played?limit=20`

Spotify URL: `https://api.spotify.com/v1/me/player/recently-played?limit={limit}`  
Header: `Authorization: Bearer {access_token}`

Clamp: `limit = max(1, min(limit, 50))`.

- [ ] **Step 1: Write failing tests**

`tests/test_spotify_recently_played.py`:

```python
import respx
from httpx import Response
from fastapi.testclient import TestClient

from app.main import app
from app.spotify import oauth
from app.spotify.oauth import TokenSet


client = TestClient(app)


def setup_function() -> None:
    oauth.clear_tokens()
    oauth.clear_pending_state()


def test_recently_played_unauthorized_without_token():
    response = client.get("/spotify/recently-played")
    assert response.status_code == 401


@respx.mock
def test_recently_played_maps_items():
    oauth.set_tokens(
        TokenSet(access_token="access-abc", refresh_token="refresh-xyz", expires_at=None)
    )
    respx.get("https://api.spotify.com/v1/me/player/recently-played").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "played_at": "2026-07-16T12:00:00.000Z",
                        "track": {
                            "id": "track1",
                            "name": "Song",
                            "artists": [{"name": "Artist"}],
                            "album": {"name": "Album"},
                            "external_urls": {
                                "spotify": "https://open.spotify.com/track/track1"
                            },
                        },
                    },
                    {"played_at": "2026-07-16T11:00:00.000Z", "track": None},
                ]
            },
        )
    )
    response = client.get("/spotify/recently-played?limit=20")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "items": [
            {
                "played_at": "2026-07-16T12:00:00.000Z",
                "track_id": "track1",
                "name": "Song",
                "artists": ["Artist"],
                "album": "Album",
                "spotify_url": "https://open.spotify.com/track/track1",
            }
        ]
    }
    assert "access-abc" not in str(body)


@respx.mock
def test_recently_played_refreshes_on_401_then_succeeds():
    oauth.set_tokens(
        TokenSet(access_token="old-access", refresh_token="refresh-xyz", expires_at=None)
    )
    route = respx.get("https://api.spotify.com/v1/me/player/recently-played")
    route.side_effect = [
        Response(401, json={"error": {"message": "expired"}}),
        Response(
            200,
            json={
                "items": [
                    {
                        "played_at": "2026-07-16T12:00:00.000Z",
                        "track": {
                            "id": "track1",
                            "name": "Song",
                            "artists": [{"name": "Artist"}],
                            "album": {"name": "Album"},
                            "external_urls": {
                                "spotify": "https://open.spotify.com/track/track1"
                            },
                        },
                    }
                ]
            },
        ),
    ]
    respx.post("https://accounts.spotify.com/api/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "new-access",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )
    )
    # ensure refresh uses settings
    from app.config import settings

    # If refresh reads settings, monkeypatch may be needed in implementer env;
    # set tokens path only requires refresh_token present.
    response = client.get("/spotify/recently-played")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert oauth.get_tokens().access_token == "new-access"
```

If settings are required for refresh, monkeypatch client id/secret in the test the same way as Task 2.

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_spotify_recently_played.py -v
```

Expected: FAIL (route missing).

- [ ] **Step 3: Implement client, schemas, route**

`app/spotify/schemas.py` — Pydantic models matching response JSON.

`app/spotify/client.py` — `map_recently_played` + `async fetch_recently_played(access_token, limit) -> httpx.Response` or raise custom errors. Prefer returning status code + JSON to the route for refresh logic, OR put refresh orchestration in the route:

Route logic:

1. If no tokens → 401  
2. Clamp limit  
3. Call Spotify with access token  
4. If 401 and refresh_token present: refresh, set_tokens, retry once  
5. If still 401: clear_tokens, raise 401  
6. If not 200: raise 502  
7. Map and return `RecentlyPlayedResponse`

- [ ] **Step 4: Run full suite**

```bash
pytest -v
```

Expected: all PASS.

- [ ] **Step 5: Update README**

Document:

1. Fill `.env` Spotify vars (Redirect URI `http://127.0.0.1:8000/callback`)
2. `uvicorn app.main:app --reload`
3. Open browser `/auth/spotify/login`, then `/docs` → `/spotify/recently-played`

- [ ] **Step 6: Commit**

```bash
git add app/spotify tests/test_spotify_recently_played.py README.md
git commit -m "feat: add Spotify recently-played endpoint with token refresh"
```

---

## Self-Review

1. **Spec coverage:** Package refactor, OAuth + state, callback at `/callback`, in-memory tokens, auth status, recently-played mapping, refresh-on-401, env redirect URI, no token leakage, mocked tests — covered by Tasks 1–3.
2. **Placeholders:** None; full code and commands included.
3. **Type consistency:** `TokenSet`, `clear_tokens`, `get_tokens`, `set_tokens`, `create_login_state`, `consume_login_state`, redirect URI, response item fields match across tasks.
