# VibeCast

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in Spotify and OpenAI keys in `.env` when needed. Never commit `.env`.

Set Spotify Redirect URI to `http://127.0.0.1:8000/callback`.

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Status: [http://127.0.0.1:8000/status](http://127.0.0.1:8000/status)

## Spotify

1. Fill `.env` with `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and set Redirect URI to `http://127.0.0.1:8000/callback`.
2. Start the server: `uvicorn app.main:app --reload`
3. Open [http://127.0.0.1:8000/auth/spotify/login](http://127.0.0.1:8000/auth/spotify/login) in your browser to authenticate.
4. Use [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to call `GET /spotify/recently-played`.
