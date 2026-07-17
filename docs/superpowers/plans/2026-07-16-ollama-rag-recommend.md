# Ollama RAG Recommend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Local Chroma index of ~1000 TMDB popular movies + Ollama RAG recommendations from Spotify listening context, exposed via API and SPA.

**Architecture:** Ingest script → Chroma at `data/chroma/`. `POST /recommend` builds mood text from Spotify, embeds via Ollama, retrieves top-k, chats for JSON picks. SPA **For your vibe** section (logged-in).

**Tech Stack:** chromadb, httpx, FastAPI, Ollama HTTP API, pytest, respx, Vite React TS

**Spec:** `docs/superpowers/specs/2026-07-16-ollama-rag-recommend-design.md`

## Global Constraints

- No fine-tuning; RAG only
- Music = Spotify session context only (not a music vector catalog)
- ~1000 TMDB popular movies; docs include title/year/genres/overview
- Chroma under `data/chroma/` (gitignored)
- Defaults: `OLLAMA_BASE_URL=http://127.0.0.1:11434`, chat `llama3.2`, embed `nomic-embed-text`
- `POST /recommend` requires Spotify auth; empty index / Ollama down → 503; chat parse fail → 502
- UI section after Top artists, before Movies search
- CI tests must mock Ollama/TMDB (no live calls required)
- Linux Node for frontend build: `PATH="$HOME/.local/node/bin:$PATH"`

## File Structure

| Path | Role |
|------|------|
| `app/config.py` | Ollama + RAG settings |
| `app/rag/*` | ingest, store, ollama, recommend, schemas, routes |
| `data/chroma/` | Persistent index (gitignored) |
| `tests/test_rag_*.py` | Unit/integration mocks |
| `frontend` | For your vibe UI |
| `.gitignore` | `data/` |
| `README.md` | ollama pull + ingest |

---

### Task 1: Config, Chroma store, Ollama client, ingest, `/rag/status`

**Files:**
- Modify: `app/config.py`, `app/main.py`, `.env.example`, `.gitignore`, local `.env`
- Create: `app/rag/__init__.py`, `store.py`, `ollama_client.py`, `ingest.py`, `schemas.py`, `routes.py` (status only first — or status + stub)
- Create: `tests/test_rag_status.py`, `tests/test_rag_mood.py` (mood builder can wait for Task 2)

**Interfaces:**
- Settings fields: `ollama_base_url`, `ollama_chat_model`, `ollama_embed_model`, `rag_collection`, `rag_movie_target`, `rag_chroma_path` (default `data/chroma`)
- `embed_texts(texts: list[str]) -> list[list[float]]` via `POST {base}/api/embeddings`
- `chat_json(prompt: str) -> str` via `POST {base}/api/chat` or `/api/generate`
- `get_collection()` Chroma persistent
- `upsert_movies(ids, documents, metadatas, embeddings)`
- `query_movies(embedding, n_results) -> docs+metadatas`
- `count_movies() -> int`
- `async def ping_ollama() -> bool`
- Ingest `__main__`: fetch popular, embed batches, upsert
- `GET /rag/status`

Note on Ollama embeddings API: use `POST /api/embeddings` with body `{"model": "...", "prompt": "..."}` returning `embedding` list. Chat: `POST /api/chat` with `{"model","messages","stream":false,"format":"json"}`.

- [ ] **Step 1: Add failing status tests**

```python
# tests/test_rag_status.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_rag_status_shape(monkeypatch):
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 0)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: False)
    r = client.get("/rag/status")
    assert r.status_code == 200
    body = r.json()
    assert body["index_ready"] is False
    assert body["document_count"] == 0
    assert body["ollama_reachable"] is False
    assert "embed_model" in body and "chat_model" in body
```

- [ ] **Step 2: RED**

```bash
pytest tests/test_rag_status.py -v
```

- [ ] **Step 3: Implement settings, store, ollama_client, status route, ingest module**

Also add TMDB popular fetch helper in `app/movies/client.py` or `app/rag/tmdb_popular.py`:

`async def fetch_popular_page(api_key, page) -> httpx.Response` → `/movie/popular`

Genre names: either include genre_ids as numbers in text or fetch `/genre/movie/list` once and map — prefer fetch genre list once during ingest.

Ingest sync/async: use `httpx` sync or `asyncio.run` for simplicity in CLI.

- [ ] **Step 4: Wire router; gitignore `data/`; env example**

- [ ] **Step 5: GREEN + full pytest**

```bash
pytest -q
```

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: add Chroma movie ingest and RAG status endpoint"
```

---

### Task 2: Recommend pipeline + tests

**Files:**
- Create/modify: `app/rag/recommend.py`, `routes.py` (POST /recommend), `schemas.py`
- Create: `tests/test_rag_recommend.py`

**Interfaces:**
- `build_mood_query(now_playing, recent, top_tracks, top_artists) -> str`
- `parse_recommendation_json(raw: str) -> list[dict]`
- `async def recommend_for_user() -> RecommendResponse` orchestration using Spotify `_authed_spotify` helpers / client fetches

**Recommend route:**
1. Spotify token required
2. Collect context via existing spotify client fetchers + map functions
3. Call recommend orchestration
4. Return schema from spec

- [ ] **Step 1: Failing unit tests for mood builder + JSON parse + recommend 401/503**

```python
def test_build_mood_query_includes_track_names():
    from app.rag.recommend import build_mood_query
    text = build_mood_query(
        now_playing_line="Now: Song by Artist",
        recent_lines=["Recent1"],
        top_track_lines=["Top1"],
        top_artist_lines=["ArtistA"],
    )
    assert "Song" in text and "Recent1" in text

def test_parse_recommendation_json_extracts_items():
    from app.rag.recommend import parse_recommendation_json
    raw = '{"items":[{"tmdb_id":1,"title":"X","reason":"y"}]}'
    items = parse_recommendation_json(raw)
    assert items[0]["tmdb_id"] == 1

def test_recommend_unauthorized():
    # no tokens
    assert client.post("/recommend").status_code == 401
```

Mock Ollama + store for happy path returning 200 with items.

- [ ] **Step 2: RED then implement recommend.py + route**

Prompt must instruct: only pick from provided candidate list; output JSON `{ "mood_summary": "...", "items": [ {"tmdb_id", "title", "reason"} ] }`.

Validate tmdb_ids against retrieved set; drop unknowns.

- [ ] **Step 3: Full pytest GREEN**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: add Spotify-to-movie RAG recommend endpoint"
```

---

### Task 3: SPA For your vibe + README

**Files:**
- `frontend/src/types.ts`, `api.ts`, `components/RecommendSection.tsx`, `App.tsx`, `styles.css`, `README.md`

- [ ] **Step 1: API `fetchRagStatus`, `requestRecommendations` (POST)**

- [ ] **Step 2: RecommendSection** — button, loading/error, results list with poster/title/year/reason; if status not ready, show ingest hint

- [ ] **Step 3: Place in App after Top artists, before Movies**

- [ ] **Step 4: README** — ollama pull, ingest, recommend flow

- [ ] **Step 5: Build + pytest**

```bash
export PATH="$HOME/.local/node/bin:$PATH"
cd frontend && npm run build
cd .. && source .venv/bin/activate && pytest -q
```

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: add For your vibe recommendations UI"
```

---

## Self-Review

1. Spec coverage: ingest, status, recommend, SPA, env, gitignore, mocks — Tasks 1–3.
2. No fine-tuning scope creep.
3. Spotify auth gate and 503/502 behavior explicit.
