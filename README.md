# VibeCast

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in Spotify and OpenAI keys in `.env` when needed. Never commit `.env`.

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
4. After authorization, you land back on the SPA with your recently played tracks.
