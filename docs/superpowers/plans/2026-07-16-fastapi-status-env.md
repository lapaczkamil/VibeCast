# FastAPI Status Server & Env Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap a single-file FastAPI app with `GET /status` and safe `.env`-based Spotify/OpenAI credentials.

**Architecture:** One `main.py` holds FastAPI app, `Settings` (pydantic-settings), and `/status`. Secrets live in gitignored `.env`; `.env.example` documents expected keys. Optional API keys so the server starts without them.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, pydantic-settings, pytest, httpx (via FastAPI TestClient)

**Spec:** `docs/superpowers/specs/2026-07-16-fastapi-status-env-design.md`

## Global Constraints

- Single-file app: `main.py` only (no package split)
- Optional at startup: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `OPENAI_API_KEY`
- Default `APP_NAME=VibeCast`
- `/status` must never return secret values or whether keys are set
- `.env` and `.venv` must be gitignored

## File Structure

| File | Responsibility |
|------|----------------|
| `.gitignore` | Ignore `.env`, `.venv`, `__pycache__`, `.pytest_cache` |
| `.env.example` | Committed template of env var names |
| `.env` | Local secrets (empty placeholders OK) |
| `main.py` | `Settings`, FastAPI `app`, `GET /status` |
| `tests/test_status.py` | Status endpoint + settings defaults |
| `requirements.txt` | Keep in sync; add `pytest` if missing |
| `README.md` | How to activate venv, copy `.env`, run server |

---

### Task 1: Secure env scaffolding

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `.env`
- Modify: `README.md`

**Interfaces:**
- Consumes: none
- Produces: env var names `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `OPENAI_API_KEY`, `APP_NAME` for Task 2

- [ ] **Step 1: Create `.gitignore`**

```gitignore
.env
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
```

- [ ] **Step 2: Create `.env.example`**

```env
APP_NAME=VibeCast
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
OPENAI_API_KEY=
```

- [ ] **Step 3: Create `.env` (same content as `.env.example` for local start)**

```env
APP_NAME=VibeCast
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
OPENAI_API_KEY=
```

- [ ] **Step 4: Update `README.md` with setup/run instructions**

```markdown
# VibeCast

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in Spotify and OpenAI keys in `.env` when needed. Never commit `.env`.

## Run

```bash
source .venv/bin/activate
uvicorn main:app --reload
```

Status: [http://127.0.0.1:8000/status](http://127.0.0.1:8000/status)
```

- [ ] **Step 5: Verify `.env` is ignored**

Run:

```bash
git check-ignore -v .env .venv
git status --short
```

Expected: both paths reported as ignored; `.env` does not appear as an untracked file to add. `.env.example` and `.gitignore` should show as untracked (`??`).

- [ ] **Step 6: Commit**

```bash
git add .gitignore .env.example README.md
git commit -m "chore: add env templates and gitignore for secrets"
```

---

### Task 2: Status endpoint with Settings

**Files:**
- Create: `main.py`
- Create: `tests/test_status.py`
- Modify: `requirements.txt` (ensure `pytest` is listed)

**Interfaces:**
- Consumes: env var names from Task 1
- Produces:
  - `class Settings(BaseSettings)` with fields `app_name: str = "VibeCast"`, `spotify_client_id: str | None = None`, `spotify_client_secret: str | None = None`, `openai_api_key: str | None = None`
  - `settings: Settings`
  - `app: FastAPI`
  - `GET /status` → `{"status": "ok", "service": <settings.app_name>}`

- [ ] **Step 1: Install pytest in the venv**

Run:

```bash
source .venv/bin/activate
pip install pytest
pip freeze --local > requirements.txt
```

Expected: `pytest` appears in `requirements.txt`; command exits 0.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_status.py`:

```python
from fastapi.testclient import TestClient

from main import app, settings


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
    assert settings.app_name == "VibeCast" or isinstance(settings.app_name, str)
    # Optional secrets must not crash startup; values may be "" or None
    assert settings.spotify_client_id in (None, "")
    assert settings.spotify_client_secret in (None, "")
    assert settings.openai_api_key in (None, "")
```

Note: If `.env` sets `APP_NAME=VibeCast` and empty secrets, empty strings are fine — treat `None` and `""` as acceptable for optional keys.

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate
pytest tests/test_status.py -v
```

Expected: FAIL with import error for `main` (module not found) or `app` not defined.

- [ ] **Step 4: Implement `main.py`**

```python
from fastapi import FastAPI
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
    openai_api_key: str | None = None


settings = Settings()
app = FastAPI(title=settings.app_name)


@app.get("/status")
def status() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate
pytest tests/test_status.py -v
```

Expected: both tests PASS.

- [ ] **Step 6: Manual smoke check**

Run server in background:

```bash
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000
```

In another shell:

```bash
curl -s http://127.0.0.1:8000/status
```

Expected JSON: `{"status":"ok","service":"VibeCast"}` (or whatever `APP_NAME` is in `.env`).

Stop the uvicorn process after the check.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_status.py requirements.txt
git commit -m "feat: add FastAPI status endpoint and env settings"
```

---

## Self-Review

1. **Spec coverage:** Status endpoint, Settings/env vars, `.env` / `.env.example`, `.gitignore`, no secret leakage, optional keys — all covered by Tasks 1–2.
2. **Placeholders:** None; full file contents and commands included.
3. **Type consistency:** `settings.app_name`, optional Spotify/OpenAI fields, `/status` shape match the spec.
