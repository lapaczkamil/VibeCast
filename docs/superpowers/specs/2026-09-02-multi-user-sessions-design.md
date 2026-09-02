# Multi-user sessions — Design

## Goal

Replace the process-global Spotify auth state with **per-user sessions** backed by SQLite, so
two people can use the app at once without seeing each other's data.

This is slice **A1** of the production track (deployment, containerization and hardening are
separate slices and depend on this one).

## Problem

Auth state today is one set of module globals shared by the whole process:

```python
# app/spotify/oauth.py
_tokens: "TokenSet | None" = None    # one token set per process
_pending_state: str | None = None    # one OAuth state per process
_refresh_lock = asyncio.Lock()       # one refresh lock per process
```

`get_tokens()` takes no user argument, `_authed_spotify` reads the global, and the upstream
cache in `app/spotify/upstream.py` is keyed by endpoint name only.

Concretely, with two users:

- B logging in **overwrites** A's tokens; A then sees B's listening history, top artists and
  now-playing.
- Two logins in flight overwrite `_pending_state`, so the CSRF check passes for whichever
  callback arrives last and is defeated for the other.
- Cached `/me`, `/recently-played` and `/currently-playing` responses are served across users.

This is a data-leak class of bug, not a scaling limit. It blocks any deployment beyond one
person on localhost.

## Decisions

| Topic | Choice |
|-------|--------|
| Session identity | Opaque 32-byte random id in an `HttpOnly; Secure; SameSite=Lax` cookie |
| Why not JWT | Tokens must be stored server-side regardless; a stateless token adds no value here |
| Storage | SQLite via stdlib `sqlite3` behind a thin repository module |
| Why not Postgres/ORM | Two tables and a dozen users; the codebase has no ORM today. Alembic + SQLAlchemy is the documented upgrade path for slice B |
| Stable user identity | Spotify `/me` `id`, fetched once at callback — re-login reuses the same user row |
| Refresh-token at rest | Encrypted with a key from `SESSION_SECRET`; DB file mode `0600` |
| Session lifetime | 30 days sliding, refreshed on use; expired rows swept on read |
| Cache isolation | Every `upstream` cache key prefixed with the user id |
| Refresh lock | One `asyncio.Lock` **per user**, not per process |
| Rate-limit block | Stays **global** — Spotify's quota is per application, not per user |
| Circuit breaker | Stays **global** for the same reason (`trip_circuit` / `is_circuit_open`) |
| Request pacer | `_pace_requests` stays **global**; it throttles the shared app quota |
| Logout | Deletes the session row and clears the cookie; tokens for that user are dropped |

## Out of scope

- Deployment, HTTPS, tunnel, containerization (slice A2)
- Ollama error handling, timeout split, `think: False` (slice A3)
- Accounts independent of Spotify, roles, admin UI
- Recommendation history and feedback — unlocked by this schema, specified separately
- Postgres, migrations tooling

## Data model

```sql
CREATE TABLE users (
    id            TEXT PRIMARY KEY,   -- Spotify user id
    display_name  TEXT,
    created_at    REAL NOT NULL,
    access_token  TEXT NOT NULL,      -- encrypted
    refresh_token TEXT,               -- encrypted
    expires_at    REAL
);

CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,     -- opaque cookie value
    user_id     TEXT REFERENCES users(id) ON DELETE CASCADE,
    oauth_state TEXT,                 -- set pre-login, cleared on callback
    created_at  REAL NOT NULL,
    last_seen   REAL NOT NULL
);

CREATE TABLE schema_version (version INTEGER NOT NULL);
```

A session row exists **before** login so the OAuth state has somewhere to live; `user_id` is
NULL until the callback succeeds.

## Auth flow

1. **Any request without a valid session cookie** gets a fresh session row and cookie.
2. `GET /auth/spotify/login` writes `oauth_state` on the caller's session, redirects to Spotify.
3. `GET /callback` looks up the session by cookie, compares `state` against that row's
   `oauth_state` (not a global), clears it, exchanges the code, fetches `/me`, upserts the
   user row and links `sessions.user_id`.
4. `_authed_spotify` resolves the caller's user from the request, loads tokens, and refreshes
   under that user's lock when expired.
5. `GET /auth/spotify/status` and `GET /spotify/session` report from the caller's own session.
6. `POST /auth/spotify/logout` deletes the session row and clears the cookie.

## Code changes

| Area | Change |
|------|--------|
| `app/db.py` *(new)* | Connection factory, schema init, `schema_version` check |
| `app/auth/repository.py` *(new)* | `create_session`, `get_session`, `touch_session`, `set_oauth_state`, `link_user`, `upsert_user`, `get_tokens_for`, `save_tokens_for`, `delete_session`, `sweep_expired` |
| `app/auth/crypto.py` *(new)* | Symmetric encrypt/decrypt for tokens, key from `SESSION_SECRET` |
| `app/auth/dependencies.py` *(new)* | FastAPI dependency resolving the cookie to a session; issues one when absent |
| `app/spotify/oauth.py` | Drop `_tokens` / `_pending_state` / global `_refresh_lock`; keep `TokenSet`, URL building and the token exchange as pure functions |
| `app/spotify/routes.py` | `_authed_spotify` takes the resolved session; per-user refresh lock; `/login`, `/callback`, `/session`, `/logout` use the repository |
| `app/spotify/upstream.py` | `get_cached`, `get_stale`, `set_cached`, `cache_age_seconds`, `invalidate_keys` take a user id and prefix keys. Circuit breaker, `_blocked_until` and `_pace_requests` stay global and untouched — they guard the shared app quota. `clear_cache()` keeps wiping everything (tests rely on it) |
| `app/rag/routes.py` | `/recommend` and `/recommend/mood-context` take the session dependency instead of reading the global |
| `app/spotify/routes.py` callers | Every `/spotify/*` route (`me`, `currently-playing`, `top/tracks`, `top/artists`, `recently-played`, `search`) passes the session through to `_authed_spotify` and to the cache keys |
| `app/config.py` | `session_secret`, `session_db_path`, `session_ttl_days`; `.env.example` mirrors them (guarded by `test_config_env_sync.py`) |
| `tests/` | Existing tests set global tokens directly — migrate to a fixture creating a session row and sending the cookie |

## Test strategy

Beyond porting the current suite, three tests define the fix:

- Two sessions with different users hit `/spotify/currently-playing`; each gets its own
  upstream response and neither sees the other's cache entry.
- Two logins in flight, callbacks arriving in reverse order, both validate against their own
  `oauth_state`; a callback carrying another session's state is rejected.
- A refresh triggered on user A does not block or mutate user B's tokens.

A fourth, easy to forget: `tests/test_spotify_dashboard.py` currently fails when run as a
suite because the upstream cache leaks between tests. Per-user keys do not fix that — the
fixture must call `clear_cache()` in `setup_function`, as `test_rag_recommend.py` already
does for the ReccoBeats cache.

## Operator steps

1. Set `SESSION_SECRET` (32+ random bytes) in `.env` — the app refuses to start without it.
2. First run creates `data/app.db`; no migration needed from the current state because no
   auth data is persisted today.
3. Everyone must log in again — existing in-memory tokens are lost on deploy anyway.

## Follow-up this unblocks

- Recommendation history and feedback (same DB, `user_id` already present)
- Excluding recently shown movies per user, which is the cheapest fix for repeated results
- Adaptive now-playing polling — at 5 s per user the shared Spotify quota breaks down around
  a dozen concurrent users, so this must land before exposure
