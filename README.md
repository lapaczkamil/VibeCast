# VibeCast

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in Spotify, OpenAI, and TMDB keys in `.env` when needed. Never commit `.env`.

For movie search, create a free TMDB API key at [https://www.themoviedb.org/settings/api](https://www.themoviedb.org/settings/api) and set `TMDB_API_KEY` in `.env`.

Set Spotify Redirect URI to `http://127.0.0.1:8000/callback` (backend callback, not the Vite dev server).

Set `FRONTEND_URL=http://127.0.0.1:5173` in `.env` so OAuth success redirects back to the SPA.

## Run

**Terminal 1 — backend**

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

**Terminal 2 — frontend**

```bash
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:5173/](http://127.0.0.1:5173/). The Vite dev server proxies `/api/*` to the FastAPI backend on port 8000.

Status: [http://127.0.0.1:8000/status](http://127.0.0.1:8000/status)

## Spotify

1. Fill `.env` with `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and set Redirect URI to `http://127.0.0.1:8000/callback`.
2. Start backend and frontend (see above).
3. Open [http://127.0.0.1:5173/](http://127.0.0.1:5173/) and click **Log in with Spotify**.
4. After authorization, you land back on the SPA with your profile, now playing, recently played, and top tracks/artists.

**After updating VibeCast:** if you were already logged in before new Spotify permissions were added, click **Log out** on the SPA, then **Log in with Spotify** again so Spotify grants the expanded scopes (`user-read-private`, `user-read-currently-playing`, `user-top-read`, etc.).

## Movie recommendations (RAG)

VibeCast can recommend movies from your Spotify listening mood using a local Chroma index and Ollama.

### 1. Pull Ollama models

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

Ensure Ollama is running (default `http://127.0.0.1:11434`). Optional env overrides: `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `OLLAMA_EMBED_MODEL`.

### 2. Build the movie index

Requires `TMDB_API_KEY` in `.env` and a reachable Ollama embed endpoint:

```bash
source .venv/bin/activate
python -m app.rag.ingest
```

This fetches ~1000 popular TMDB movies into `data/chroma/` (gitignored). Re-running is safe.

Check readiness: [http://127.0.0.1:8000/rag/status](http://127.0.0.1:8000/rag/status) — `index_ready` should be `true` when ingest finished.

### 3. Recommend flow

1. Start backend and frontend (see **Run** above).
2. Log in with Spotify on the SPA.
3. Scroll to **For your vibe** (after Top artists, before Movies search).
4. Click **Recommend movies**.

The backend gathers now playing, recently played, and top tracks/artists, retrieves similar movies from Chroma, and asks Ollama for 3–5 picks with short reasons.

If the index is missing or Ollama is down, the UI shows a hint and `POST /recommend` returns `503`. Without Spotify auth, it returns `401`.
