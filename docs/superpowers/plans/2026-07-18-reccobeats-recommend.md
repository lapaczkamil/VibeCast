# ReccoBeats Recommend Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich `POST /recommend` with ReccoBeats audio features: NL mood profile for embeddings + post-Chroma genre rerank, with soft-fail if ReccoBeats is unavailable.

**Architecture:** New `app/reccobeats/` package (client, schemas, mood, rerank). `recommend.py` fetches features for the seed Spotify id, appends an audio profile to `mood_query`, queries Chroma with enlarged top-K, reranks to 8, then existing LLM path. No frontend changes.

**Tech Stack:** FastAPI, httpx, pytest, respx, existing Ollama/Chroma recommend pipeline

**Spec:** `docs/superpowers/specs/2026-07-18-reccobeats-recommend-design.md`

## Global Constraints

- Soft-fail ReccoBeats: never fail recommend solely because features are missing
- `MAX_SEEDS = 1`; use seed Spotify `id` for ReccoBeats
- FE request/response contracts unchanged
- No Spotify upstream circuit coupling for ReccoBeats HTTP
- Genres for rerank come from document text (`Genres: …`), not Chroma metadata (ingest does not store genres in metadata)
- CI must not call live ReccoBeats (mock with respx/monkeypatch)

## File Structure

| Path | Role |
|------|------|
| `app/config.py` | `reccobeats_base_url`, `reccobeats_timeout_seconds` |
| `app/reccobeats/schemas.py` | `AudioFeatures` model |
| `app/reccobeats/client.py` | Fetch + in-memory cache |
| `app/reccobeats/mood.py` | Features → NL audio profile line |
| `app/reccobeats/rerank.py` | Parse genres + score/reorder candidates |
| `app/rag/recommend.py` | Wire fetch → enrich mood → enlarge Chroma → rerank |
| `tests/test_reccobeats_mood.py` | Mood descriptor unit tests |
| `tests/test_reccobeats_rerank.py` | Rerank unit tests |
| `tests/test_reccobeats_client.py` | Client HTTP + cache + soft errors |
| `tests/test_rag_recommend.py` | Integration: features in mood path; soft-fail still 200 |

---

### Task 1: Config + AudioFeatures schema + mood descriptors

**Files:**
- Modify: `app/config.py`
- Create: `app/reccobeats/__init__.py` (empty or re-exports)
- Create: `app/reccobeats/schemas.py`
- Create: `app/reccobeats/mood.py`
- Test: `tests/test_reccobeats_mood.py`

**Interfaces:**
- Consumes: none
- Produces:
  - `Settings.reccobeats_base_url: str` default `"https://api.reccobeats.com"`
  - `Settings.reccobeats_timeout_seconds: float` default `4.0`
  - `class AudioFeatures(BaseModel)` with fields: `acousticness`, `danceability`, `energy`, `instrumentalness`, `liveness`, `speechiness`, `valence` (`float | None`), `tempo`, `loudness` (`float | None`), `key`, `mode` (`int | None`), optional `id: str | None = None`
  - `def format_audio_profile(features: AudioFeatures) -> str` — single line or short multi-clause string starting conceptually as profile text without the `Audio profile:` prefix (caller adds prefix) OR include prefix consistently — **use:** return body only, e.g. `"high energy, dark/low valence, moderate tempo (~92 BPM), low danceability, mostly acoustic"`

- [ ] **Step 1: Write failing mood tests**

```python
# tests/test_reccobeats_mood.py
from app.reccobeats.mood import format_audio_profile
from app.reccobeats.schemas import AudioFeatures


def test_format_audio_profile_high_energy_low_valence():
    features = AudioFeatures(
        energy=0.9,
        valence=0.15,
        danceability=0.2,
        acousticness=0.8,
        instrumentalness=0.1,
        tempo=92.0,
        speechiness=0.05,
        liveness=0.1,
        loudness=-8.0,
        key=5,
        mode=0,
    )
    text = format_audio_profile(features).lower()
    assert "high energy" in text or "intense" in text
    assert "dark" in text or "melancholic" in text or "low valence" in text
    assert "92" in text
    assert "acoustic" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reccobeats_mood.py -v`  
Expected: FAIL (import / module missing)

- [ ] **Step 3: Add config fields**

In `app/config.py` `Settings`:

```python
reccobeats_base_url: str = "https://api.reccobeats.com"
reccobeats_timeout_seconds: float = 4.0
```

- [ ] **Step 4: Implement schemas + mood**

Create `app/reccobeats/schemas.py` with `AudioFeatures` as above (all feature floats optional-friendly with defaults `None` where needed; tests may pass explicit values).

Create `app/reccobeats/mood.py` with threshold helpers, e.g.:

```python
def _band(value: float | None, low: float, high: float) -> str:
    if value is None:
        return "mid"
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "mid"
```

Map bands to phrases per spec table (energy low/mid/high → calm / balanced energy / high energy; valence → dark/melancholic / emotionally mixed / bright/uplifting; etc.). Tempo: `<90` slow, `90–120` moderate with `(~{int(tempo)} BPM)`, `>120` fast. Skip clauses when value is `None`. Join with `", "`.

- [ ] **Step 5: Run mood tests**

Run: `pytest tests/test_reccobeats_mood.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/config.py app/reccobeats/schemas.py app/reccobeats/mood.py app/reccobeats/__init__.py tests/test_reccobeats_mood.py
git commit -m "feat: add ReccoBeats audio profile mood formatting"
```

---

### Task 2: ReccoBeats HTTP client + cache

**Files:**
- Create: `app/reccobeats/client.py`
- Test: `tests/test_reccobeats_client.py`

**Interfaces:**
- Consumes: `AudioFeatures`, `settings.reccobeats_base_url`, `settings.reccobeats_timeout_seconds`
- Produces:
  - `async def fetch_audio_features(spotify_track_id: str) -> AudioFeatures | None`
  - Module-level cache: `(track_id -> (expires_at: float, features: AudioFeatures))`, TTL `3600` seconds
  - `def clear_audio_features_cache() -> None` for tests

Behavior:
- `GET {base}/v1/audio-features?ids={id}` with header `Accept: application/json`
- Parse JSON `content` list; take first object; map into `AudioFeatures`
- On timeout, HTTP error, empty content, parse error → return `None` (optionally `logging.warning`)
- Cache only successful non-`None` results
- Cache hit returns without network

- [ ] **Step 1: Write failing client tests**

```python
# tests/test_reccobeats_client.py
import respx
from httpx import Response

from app.reccobeats import client as rb_client


def setup_function() -> None:
    rb_client.clear_audio_features_cache()


@respx.mock
async def test_fetch_audio_features_success():
    respx.get("https://api.reccobeats.com/v1/audio-features").mock(
        return_value=Response(
            200,
            json={
                "content": [
                    {
                        "id": "s1",
                        "energy": 0.8,
                        "valence": 0.2,
                        "danceability": 0.3,
                        "acousticness": 0.1,
                        "instrumentalness": 0.0,
                        "speechiness": 0.05,
                        "liveness": 0.1,
                        "tempo": 120.0,
                        "loudness": -5.0,
                        "key": 1,
                        "mode": 1,
                    }
                ]
            },
        )
    )
    features = await rb_client.fetch_audio_features("s1")
    assert features is not None
    assert features.energy == 0.8
    assert features.valence == 0.2


@respx.mock
async def test_fetch_audio_features_404_returns_none():
    respx.get("https://api.reccobeats.com/v1/audio-features").mock(
        return_value=Response(404, json={"detail": "not found"})
    )
    assert await rb_client.fetch_audio_features("missing") is None


@respx.mock
async def test_fetch_audio_features_uses_cache():
    route = respx.get("https://api.reccobeats.com/v1/audio-features").mock(
        return_value=Response(
            200,
            json={"content": [{"energy": 0.5, "valence": 0.5, "tempo": 100.0}]},
        )
    )
    await rb_client.fetch_audio_features("cached")
    await rb_client.fetch_audio_features("cached")
    assert route.call_count == 1
```

If project tests are sync-only, wrap with `pytest.mark.anyio` / `asyncio.run` consistent with existing async tests — check how other httpx async tests run (`pytest-asyncio` or sync TestClient only). Prefer:

```python
import pytest

@pytest.mark.asyncio
async def test_...
```

If asyncio plugin missing, use:

```python
import asyncio
def test_fetch_audio_features_success():
    asyncio.run(_test())
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_reccobeats_client.py -v`

- [ ] **Step 3: Implement `client.py`**

```python
import logging
import time
from typing import Any

import httpx

from app.config import settings
from app.reccobeats.schemas import AudioFeatures

logger = logging.getLogger(__name__)
_CACHE_TTL_SECONDS = 3600.0
_cache: dict[str, tuple[float, AudioFeatures]] = {}


def clear_audio_features_cache() -> None:
    _cache.clear()


def _parse_features(payload: dict[str, Any]) -> AudioFeatures | None:
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        return None
    item = content[0]
    if not isinstance(item, dict):
        return None
    return AudioFeatures.model_validate(item)


async def fetch_audio_features(spotify_track_id: str) -> AudioFeatures | None:
    track_id = (spotify_track_id or "").strip()
    if not track_id:
        return None
    cached = _cache.get(track_id)
    if cached and cached[0] > time.time():
        return cached[1]
    url = f"{settings.reccobeats_base_url.rstrip('/')}/v1/audio-features"
    try:
        async with httpx.AsyncClient(
            timeout=settings.reccobeats_timeout_seconds
        ) as http:
            response = await http.get(
                url,
                params={"ids": track_id},
                headers={"Accept": "application/json"},
            )
        if response.status_code != 200:
            logger.warning(
                "ReccoBeats audio-features failed track=%s status=%s",
                track_id,
                response.status_code,
            )
            return None
        features = _parse_features(response.json())
        if features is None:
            return None
        _cache[track_id] = (time.time() + _CACHE_TTL_SECONDS, features)
        return features
    except Exception as exc:
        logger.warning(
            "ReccoBeats audio-features error track=%s err=%s",
            track_id,
            exc,
        )
        return None
```

Adjust `AudioFeatures` to allow partial payloads (`model_config` extra ignore; optional fields default `None`).

- [ ] **Step 4: Run client tests — expect PASS**

Run: `pytest tests/test_reccobeats_client.py -v`

- [ ] **Step 5: Commit**

```bash
git add app/reccobeats/client.py tests/test_reccobeats_client.py
git commit -m "feat: add ReccoBeats audio-features client with cache"
```

---

### Task 3: Genre parse + rerank

**Files:**
- Create: `app/reccobeats/rerank.py`
- Test: `tests/test_reccobeats_rerank.py`

**Interfaces:**
- Consumes: `AudioFeatures`
- Produces:
  - `def genres_from_document(document: str) -> list[str]`
  - `def rerank_candidates(documents: list[str], metadatas: list[dict], features: AudioFeatures, keep: int = 8) -> tuple[list[str], list[dict]]`

`genres_from_document`: find line starting with `Genres:`, split on commas, strip; return `[]` if missing.

Affinity (additive score): start each candidate with `base = len(documents) - index` (preserve Chroma preference). Add boosts when feature thresholds match genre tokens (case-insensitive substring or exact TMDB names):

```python
# Example constants in rerank.py
HIGH_ENERGY_GENRES = {"Action", "Adventure", "Thriller", "Science Fiction"}
LOW_VALENCE_GENRES = {"Drama", "Horror", "Crime", "War"}
HIGH_VALENCE_GENRES = {"Comedy", "Romance", "Family", "Animation"}
HIGH_ACOUSTIC_GENRES = {"Documentary", "Drama", "Music", "History"}
HIGH_DANCE_GENRES = {"Music", "Comedy", "Romance"}
```

Thresholds: energy `>0.65`, valence `<0.35` / `>0.65`, acousticness `>0.55`, danceability `>0.65`. Boost `+3` per matching genre in the document’s genre list (cap optional). Sort by score desc; stable tie-break by original index; return first `keep` docs+metas.

When `features` is unused path — caller skips rerank. Function always requires features.

- [ ] **Step 1: Write failing rerank tests**

```python
from app.reccobeats.rerank import genres_from_document, rerank_candidates
from app.reccobeats.schemas import AudioFeatures


def test_genres_from_document():
    doc = "Fight Club (1999)\nGenres: Drama, Thriller\nOverview: ..."
    assert genres_from_document(doc) == ["Drama", "Thriller"]


def test_rerank_boosts_high_energy_action():
    docs = [
        "Calm Film\nGenres: Drama\nOverview: x",
        "Loud Film\nGenres: Action, Thriller\nOverview: y",
    ]
    metas = [{"tmdb_id": 1, "title": "Calm"}, {"tmdb_id": 2, "title": "Loud"}]
    features = AudioFeatures(energy=0.95, valence=0.5, danceability=0.4, acousticness=0.1)
    out_docs, out_metas = rerank_candidates(docs, metas, features, keep=2)
    assert out_metas[0]["tmdb_id"] == 2
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_reccobeats_rerank.py -v`

- [ ] **Step 3: Implement `rerank.py`**

Implement `genres_from_document` and `rerank_candidates` per interfaces above.

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_reccobeats_rerank.py -v`

- [ ] **Step 5: Commit**

```bash
git add app/reccobeats/rerank.py tests/test_reccobeats_rerank.py
git commit -m "feat: rerank movie candidates using ReccoBeats feature affinity"
```

---

### Task 4: Wire into `recommend_for_user`

**Files:**
- Modify: `app/rag/recommend.py`
- Modify: `tests/test_rag_recommend.py`

**Interfaces:**
- Consumes: `fetch_audio_features`, `format_audio_profile`, `rerank_candidates`
- Produces: same `recommend_for_user` public behavior; enlarged retrieve then rerank when features exist

Constants:

```python
RAG_TOP_K = 8
RAG_FETCH_K = 16  # Chroma fetch before rerank
```

In `recommend_for_user`, after building base `mood_query` from seeds / now-playing:

```python
features = None
seed_id: str | None = seeds[0].id if seeds else None
# If fallback now-playing only, mood has no seed id in request — skip ReccoBeats unless you also resolve now-playing id (v1: only when seeds non-empty)
if seed_id:
    features = await fetch_audio_features(seed_id)
if features is not None:
    profile = format_audio_profile(features)
    if profile:
        mood_query = f"{mood_query}\nAudio profile: {profile}"

embedding = embed_texts([mood_query])[0]
fetch_k = RAG_FETCH_K if features is not None else RAG_TOP_K
documents, metadatas = query_movies(embedding, fetch_k)
if features is not None and documents:
    documents, metadatas = rerank_candidates(
        documents, metadatas, features, keep=RAG_TOP_K
    )
else:
    documents, metadatas = documents[:RAG_TOP_K], metadatas[:RAG_TOP_K]
```

Then existing chat / map / enrich.

- [ ] **Step 1: Extend happy-path test to assert ReccoBeats is consulted and prompt can include profile**

In `tests/test_rag_recommend.py`, for seeded recommend:

```python
@respx.mock
def test_recommend_enriches_mood_with_reccobeats(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)

    captured: dict = {}

    def fake_embed(texts):
        captured["mood"] = texts[0]
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr("app.rag.recommend.embed_texts", fake_embed)
    monkeypatch.setattr(
        "app.rag.recommend.query_movies",
        lambda embedding, n_results: (
            [
                "A\nGenres: Drama\nOverview: a",
                "B\nGenres: Action, Thriller\nOverview: b",
            ],
            [
                {"tmdb_id": 1, "title": "A", "year": "2000", "poster_path": "", "rating": 7.0},
                {"tmdb_id": 2, "title": "B", "year": "2001", "poster_path": "", "rating": 7.1},
            ],
        ),
    )

    def fake_chat(prompt: str) -> str:
        captured["prompt"] = prompt
        return json.dumps(
            {
                "mood_summary": "Intense",
                "items": [{"tmdb_id": 2, "title": "B", "reason": "energy match"}],
            }
        )

    monkeypatch.setattr("app.rag.recommend.chat_json", fake_chat)

    respx.get("https://api.reccobeats.com/v1/audio-features").mock(
        return_value=Response(
            200,
            json={
                "content": [
                    {
                        "energy": 0.95,
                        "valence": 0.2,
                        "danceability": 0.3,
                        "acousticness": 0.1,
                        "tempo": 140.0,
                    }
                ]
            },
        )
    )

    response = client.post(
        "/recommend",
        json={"tracks": [{"id": "seed1", "name": "Loud", "artists": ["X"]}]},
    )
    assert response.status_code == 200
    assert "Audio profile:" in captured["mood"]
    assert "energy" in captured["mood"].lower() or "intense" in captured["mood"].lower() or "high energy" in captured["mood"].lower()
```

- [ ] **Step 2: Soft-fail test**

```python
@respx.mock
def test_recommend_soft_fails_reccobeats(monkeypatch):
    # same stubs as happy path but ReccoBeats 500
    respx.get("https://api.reccobeats.com/v1/audio-features").mock(
        return_value=Response(500, text="nope")
    )
    # ... stubs for embed/query/chat ...
    response = client.post(
        "/recommend",
        json={"tracks": [{"id": "seed1", "name": "Loud", "artists": ["X"]}]},
    )
    assert response.status_code == 200
    assert "Audio profile:" not in captured["mood"]
```

- [ ] **Step 3: Run new tests — expect FAIL (not wired)**

Run: `pytest tests/test_rag_recommend.py::test_recommend_enriches_mood_with_reccobeats tests/test_rag_recommend.py::test_recommend_soft_fails_reccobeats -v`

- [ ] **Step 4: Wire `recommend.py` as specified**

Import and integrate; keep existing tests green (happy path without asserting ReccoBeats still works — may hit live URL unless mocked). **Update existing `@respx.mock` recommend tests** that post with tracks to also mock ReccoBeats `200` empty or `404`, so they stay offline:

```python
respx.get("https://api.reccobeats.com/v1/audio-features").mock(
    return_value=Response(404)
)
```

Add this to every seeded `/recommend` test that uses `@respx.mock`.

- [ ] **Step 5: Run full recommend + reccobeats suites**

Run: `pytest tests/test_rag_recommend.py tests/test_reccobeats_mood.py tests/test_reccobeats_client.py tests/test_reccobeats_rerank.py -v`  
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add app/rag/recommend.py tests/test_rag_recommend.py
git commit -m "feat: enrich recommend with ReccoBeats features and rerank"
```

---

### Task 5: Manual smoke (optional checkpoint)

- [ ] **Step 1:** With uvicorn + Ollama + ingest index, login, drop a track, run Recommend; confirm backend logs show ReccoBeats success or soft-fail without 5xx.
- [ ] **Step 2:** No FE changes required.

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| `app/reccobeats` client/schemas/mood/rerank | 1–3 |
| Config base URL + timeout | 1 |
| Enrich mood_query | 4 |
| Soft-fail | 2, 4 |
| Enlarged Chroma + rerank to 8 | 3, 4 |
| Cache ~1h | 2 |
| Unit + integration tests | 1–4 |
| No FE / no re-ingest | N/A (explicit non-goals) |

## Self-review notes

- No TBD placeholders
- Genres parsed from documents (matches current ingest metadata)
- ReccoBeats only for seeded recommend path with Spotify id (now-playing-only fallback remains title line without features in v1 — consistent with soft optional enrichment)
