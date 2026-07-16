# VibeCast — FastAPI status server & env config

**Date:** 2026-07-16  
**Status:** Approved for planning

## Goal

Bootstrap a minimal FastAPI server that exposes a health/status endpoint and loads API credentials from a local `.env` file (never committed).

## Scope

In scope:
- Single-file FastAPI app (`main.py`)
- `GET /status` returning service health (no secrets)
- Settings via `pydantic-settings` from `.env`
- `.env.example` template for Spotify + OpenAI keys
- `.gitignore` excluding `.env` and `.venv`

Out of scope:
- Spotify or OpenAI API calls
- Auth, database, packaging into multiple modules
- Production deployment config

## Architecture

Minimal monolith:

| File | Role |
|------|------|
| `main.py` | FastAPI app, `Settings`, `GET /status` |
| `.env` | Local secrets (gitignored) |
| `.env.example` | Committed placeholders |
| `.gitignore` | Ignores `.env`, `.venv`, caches |

`Settings` is instantiated once at module load and used by the app. Keys are optional so the server starts without credentials; validation happens later when those integrations are used.

## API

### `GET /status`

Response example:

```json
{
  "status": "ok",
  "service": "VibeCast"
}
```

- Does not return API keys or whether keys are set
- `service` comes from `APP_NAME` (default `VibeCast`)

## Environment variables

| Variable | Required at startup | Purpose |
|----------|---------------------|---------|
| `SPOTIFY_CLIENT_ID` | No | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | No | Spotify app client secret |
| `OPENAI_API_KEY` | No | OpenAI chat API key |
| `APP_NAME` | No (default `VibeCast`) | Service name in status |

## Security

- `.env` is gitignored; only `.env.example` is committed
- Status endpoint never exposes secret values
- No logging of secret values

## Run (after implementation)

```bash
source .venv/bin/activate
uvicorn main:app --reload
```

Then: `GET http://127.0.0.1:8000/status`

## Success criteria

1. Server starts with empty optional keys
2. `/status` returns `status: ok` and service name
3. Secrets live only in `.env`; `.env.example` documents expected keys
4. Accidental `git add .` does not stage `.env` or `.venv`
