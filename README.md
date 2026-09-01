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

This **rebuilds** `data/chroma/` from a mix of ~70% well-rated TMDB discover movies (`vote_count ≥ 200`) and ~30% popular titles (~`RAG_MOVIE_TARGET`, default 5000). Re-running wipes the previous collection and re-indexes.

Each document also carries TMDB keywords and the tagline, which supply the tonal vocabulary that plot summaries lack (`RAG_ENRICH_DOCUMENTS=false` to skip; it costs one extra TMDB call per movie, fetched with `RAG_ENRICH_WORKERS` threads).

Check readiness: [http://127.0.0.1:8000/rag/status](http://127.0.0.1:8000/rag/status) — `index_ready` should be `true` when ingest finished.

### 3. Evaluating retrieval

Retrieval quality is measured on its own, before the LLM selection step:

```bash
python -m app.rag.evaluate --variant hyde -k 8
```

`eval/dataset.json` holds the relevance judgements — **edit it**, it encodes taste and is
meant to be owned. Two metrics are reported:

- `genre_p@k` — share of candidates landing in the expected tonal neighbourhood. The
  headline number; exact-id recall is near-unhittable against a 5000 movie index.
- `recall@k` / `MRR` — against the hand-picked `relevant` ids. Sparse and strict, useful
  as a tiebreaker between variants that score alike on `genre_p`.

Variants: `dense` (embed the mood directly), `hyde` (rewrite the mood into a movie-shaped
document first, the default in the app), `hyde_lyrics` (same, with the track's lyrics in the
prompt), `hyde_mood` (blend both embeddings), `hybrid` (dense + BM25 fused with RRF),
`hyde_hybrid`. `--collection` compares two indexes.

HyDE is a single LLM generation, so per-query scores swing between runs. Compare variants
on several runs, not one.

### 4. Recommend flow

1. Start backend and frontend (see **Run** above).
2. Log in with Spotify on the SPA.
3. Scroll to **For your vibe** (after Top artists, before Movies search).
4. Click **Recommend movies**.

The backend turns the listening mood into a hypothetical movie description (HyDE), retrieves against that, reranks with the track's audio features, and asks Ollama for 3–5 picks with short reasons. Set `RAG_HYDE_ENABLED=false` to embed the raw mood instead — cheaper by one LLM call, but measurably worse. `LYRICS_ENABLED=true` adds the track's lyrics to the HyDE prompt, looked up on [LRCLIB](https://lrclib.net) (no API key; instrumentals and misses are skipped, repeated lines dropped, capped by `LYRICS_MAX_CHARS`). It is **off by default**: on the eval set it scored 0.745 against 0.880 for HyDE alone, though the metric only sees genres and lyrics mostly change theme.

If the index is missing or Ollama is down, the UI shows a hint and `POST /recommend` returns `503`. Without Spotify auth, it returns `401`.
