# VibeCast — Local Ollama RAG (music mood → movies)

**Date:** 2026-07-16  
**Status:** Approved for planning

## Product context

VibeCast recommends movies from the mood of the user’s music. This slice adds **local RAG** (not model fine-tuning): index ~1000 popular TMDB movies, retrieve by Spotify listening context, generate recommendations with Ollama.

## Goal

Ship an ingestible Chroma index of popular movies, a `POST /recommend` pipeline (Spotify context → retrieve → Ollama chat), and a logged-in SPA section that shows recommendations.

## Clarification: RAG vs training

This design does **not** fine-tune or train an LLM. Ollama serves:
1. An **embedding** model to vectorize movie documents and queries
2. A **chat** model to turn retrieved movies + music context into short recommendations

Music is used as **query context** (recent / tops / now playing), not as a full-world music catalog in the vector store.

## Scope

In scope:
- Script `python -m app.rag.ingest` to fetch ~1000 popular TMDB movies and build Chroma at `data/chroma/`
- Document text: title, year, genres, overview (and ids/poster path in metadata)
- `GET /rag/status` — index count, Ollama reachable flags (no secrets)
- `POST /recommend` — requires Spotify auth; returns 3–5 movies with reasons
- SPA section **For your vibe** (logged-in only)
- Env for Ollama models/base URL; gitignore `data/`
- Tests with mocked Ollama + Chroma fixtures where practical

Out of scope:
- Fine-tuning / LoRA
- Indexing all TMDB or a global music catalog
- LangChain / LlamaIndex as required dependencies
- Streaming chat UI
- OpenAI for this path (keep `OPENAI_API_KEY` unused here)

## Architecture

```
TMDB popular pages ──ingest──► Chroma (data/chroma)
                                      ▲
Spotify session context ──embed───────┘ retrieve top-k
                                      │
                                      ▼
                              Ollama chat → JSON recommendations
                                      │
                              POST /recommend → SPA
```

| Piece | Choice |
|-------|--------|
| Vector store | Chroma persistent client under `data/chroma/` |
| Embeddings | Ollama `nomic-embed-text` (configurable) |
| Chat | Ollama `llama3.2` (configurable) |
| Ollama HTTP | `http://127.0.0.1:11434` default |
| Movie source | TMDB `/movie/popular` paginated until ~1000 unique ids |
| Music | Build a short mood string from now playing + recent + top tracks/artists |

Package layout:

```
app/rag/
  __init__.py
  config helpers via app.config.Settings
  ingest.py          # CLI entry
  store.py           # Chroma open/query/upsert
  ollama_client.py   # embed + chat
  recommend.py       # orchestration
  schemas.py
  routes.py          # /rag/status, /recommend
```

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `TMDB_API_KEY` | (required for ingest) | Fetch movies |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API |
| `OLLAMA_CHAT_MODEL` | `llama3.2` | Recommendations |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embeddings |
| `RAG_COLLECTION` | `movies` | Chroma collection name |
| `RAG_MOVIE_TARGET` | `1000` | Approx movies to ingest |

## Ingest

Command:

```bash
source .venv/bin/activate
python -m app.rag.ingest
```

Behavior:
1. Require `TMDB_API_KEY` and reachable Ollama embed endpoint
2. Page TMDB popular until ~`RAG_MOVIE_TARGET` unique movies with non-empty overview preferred
3. Each document: `Title (year)\nGenres: ...\nOverview: ...`
4. Metadata: `tmdb_id`, `title`, `year`, `poster_path` (if any)
5. Upsert into Chroma; idempotent re-run OK (overwrite by id)
6. Print summary: documents indexed, path

Rate-limit politely toward TMDB (small sleep between pages).

## API

### `GET /rag/status`

```json
{
  "index_ready": true,
  "document_count": 1000,
  "ollama_reachable": true,
  "embed_model": "nomic-embed-text",
  "chat_model": "llama3.2"
}
```

- `index_ready`: collection exists and `document_count > 0`
- Ollama ping: lightweight tags/version or embed of a probe string; failure → `ollama_reachable: false` (still HTTP 200)
- Never expose API keys

### `POST /recommend`

Requires Spotify tokens in memory (same as other Spotify routes).  

Steps:
1. If no Spotify session → `401`
2. If index empty → `503` “Movie index not built; run ingest”
3. If Ollama unreachable → `503`
4. Gather Spotify context (reuse existing client helpers): now playing, recently played (limit ~10), top tracks/artists (limit ~5)
5. Build mood query text (titles, artists, genres if available)
6. Embed query; retrieve top-k (default 8) movie docs from Chroma
7. Chat completion with constrained prompt: return JSON list of 3–5 picks from **retrieved** candidates only, each with `tmdb_id`, `title`, `reason`
8. Map to response including `poster_url` from metadata when possible

Response shape:

```json
{
  "mood_summary": "short string",
  "items": [
    {
      "tmdb_id": 123,
      "title": "string",
      "year": "2010",
      "poster_url": "string | null",
      "reason": "string"
    }
  ]
}
```

On chat parse failure: `502` with safe message (or fallback: return top retrieved without LLM reasons — prefer 502 for honesty in v1).

## UI

Logged-in only, after Movies search (or before — prefer **after Top artists, before Movies search**, titled **For your vibe**):

- Button “Recommend movies”
- Loading / error / empty states
- Results: title, year, poster, reason
- Show note if `/rag/status` says index not ready

Logged-out: no recommend UI (Spotify required).

Preserve listening-room visual language; no fake AI badge clutter.

## Security & ops

- `data/` gitignored
- Keys stay server-side
- Recommendations require local Ollama; document `ollama pull` for chat + embed models in README

## Testing

- Unit: mood string builder; parse LLM JSON; map retrieved → response
- Integration with mocks: Chroma query stubbed / temp dir; Ollama httpx mocked
- Ingest: optional small fixture (skip live TMDB in CI)
- Frontend: build must pass

## Success criteria

1. After ingest + Ollama models pulled, `/rag/status` shows ready
2. Logged-in user can POST `/recommend` and see picks in SPA
3. Without index or Ollama, clear 503 + UI error
4. Without Spotify, 401
5. Backend tests pass without live Ollama/TMDB in CI (mocks)

## Run notes

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
python -m app.rag.ingest
uvicorn app.main:app --reload
# SPA: Recommend movies
```
