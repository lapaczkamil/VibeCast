# RAG Catalog Ingest (70/30 + Rebuild) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Chroma movie index from a ~70% TMDB discover (high-rated) + ~30% popular mix so recommendations stop drowning in 2025/26 popular fluff.

**Architecture:** Add discover page fetch; reset the Chroma collection at ingest start; replace popular-only `_collect_movies` with a two-source collector (discover quota first, popular fill, dedupe by `tmdb_id`). Document shape and recommend pipeline stay unchanged.

**Tech Stack:** FastAPI app packages, httpx, chromadb, pytest, respx (optional for HTTP)

**Spec:** `docs/superpowers/specs/2026-07-18-rag-catalog-ingest-design.md`

## Global Constraints

- Mix: ~70% discover / ~30% popular of `RAG_MOVIE_TARGET`
- Discover: `language=en-US`, `include_adult=false`, `include_video=false`, `sort_by=vote_average.desc`, `vote_count.gte=200`
- Full rebuild: wipe collection before indexing
- Skip movies with empty overview (unchanged)
- Document/metadata schema unchanged (no recommend code changes)
- Hardcode discover share `0.7` and vote threshold `200` in ingest (no new env knobs in v1)
- Operator must re-run `python -m app.rag.ingest` after merge

## File Structure

| File | Role |
|------|------|
| `app/movies/client.py` | `fetch_discover_movie_page_sync` (+ async twin if mirroring popular) |
| `app/rag/store.py` | `reset_collection()` |
| `app/rag/ingest.py` | Mix collector; call reset in `run_ingest` |
| `tests/test_rag_ingest.py` | Collector + reset tests |
| `README.md` | Document mix + rebuild |

---

### Task 1: Discover client, reset_collection, mix collector

**Files:**
- Modify: `app/movies/client.py`
- Modify: `app/rag/store.py`
- Modify: `app/rag/ingest.py`
- Create: `tests/test_rag_ingest.py`

**Interfaces:**
- Consumes: existing `fetch_popular_page_sync`, `_map_year`, `_map_rating`, `map_genre_ids`, `upsert_movies`, `settings.rag_collection`, `settings.rag_chroma_path`
- Produces:
  - `def fetch_discover_movie_page_sync(api_key: str, page: int) -> httpx.Response`
  - `def reset_collection() -> None`
  - `DISCOVER_SHARE = 0.7`, `DISCOVER_VOTE_COUNT_GTE = 200` in `ingest.py`
  - `def _collect_movies(api_key, genre_map, target) -> list[dict]` — mix collector (same movie dict shape as today)

- [ ] **Step 1: Write failing tests**

Create `tests/test_rag_ingest.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from app.rag import ingest as ingest_mod
from app.rag import store as store_mod


def _movie_result(movie_id: int, title: str, overview: str = "Plot.") -> dict:
    return {
        "id": movie_id,
        "title": title,
        "release_date": "2010-01-01",
        "overview": overview,
        "poster_path": f"/{movie_id}.jpg",
        "vote_average": 8.0,
        "genre_ids": [18],
    }


def _page_response(results: list[dict], page: int = 1, total_pages: int = 1) -> httpx.Response:
    return httpx.Response(
        200,
        json={"page": page, "total_pages": total_pages, "results": results},
    )


def test_collect_movies_prefers_discover_then_popular(monkeypatch):
    genre_map = {18: "Drama"}

    def fake_discover(api_key: str, page: int) -> httpx.Response:
        assert page == 1
        return _page_response(
            [
                _movie_result(1, "Discover One"),
                _movie_result(2, "Discover Two"),
                _movie_result(3, "Discover Three"),
            ]
        )

    def fake_popular(api_key: str, page: int) -> httpx.Response:
        assert page == 1
        return _page_response(
            [
                _movie_result(2, "Dup Popular"),  # already from discover
                _movie_result(10, "Popular Ten"),
                _movie_result(11, "Popular Eleven"),
            ]
        )

    monkeypatch.setattr(ingest_mod, "fetch_discover_movie_page_sync", fake_discover)
    monkeypatch.setattr(ingest_mod, "fetch_popular_page_sync", fake_popular)

    movies = ingest_mod._collect_movies("key", genre_map, target=4)
    ids = [m["tmdb_id"] for m in movies]
    assert ids == [1, 2, 3, 10]
    assert all(m["overview"] for m in movies)
    assert movies[0]["genre_names"] == ["Drama"]


def test_collect_movies_skips_empty_overview(monkeypatch):
    genre_map: dict[int, str] = {}

    def fake_discover(api_key: str, page: int) -> httpx.Response:
        return _page_response(
            [
                _movie_result(1, "Has Plot"),
                _movie_result(2, "No Plot", overview=""),
            ]
        )

    def fake_popular(api_key: str, page: int) -> httpx.Response:
        return _page_response([_movie_result(3, "Popular")])

    monkeypatch.setattr(ingest_mod, "fetch_discover_movie_page_sync", fake_discover)
    monkeypatch.setattr(ingest_mod, "fetch_popular_page_sync", fake_popular)

    movies = ingest_mod._collect_movies("key", genre_map, target=2)
    assert [m["tmdb_id"] for m in movies] == [1, 3]


def test_collect_movies_discover_quota_uses_ceil(monkeypatch):
    """target=5 → discover quota ceil(0.7*5)=4, then 1 from popular."""
    genre_map: dict[int, str] = {}
    discover_calls: list[int] = []

    def fake_discover(api_key: str, page: int) -> httpx.Response:
        discover_calls.append(page)
        return _page_response(
            [_movie_result(i, f"D{i}") for i in range(1, 6)],
            page=1,
            total_pages=1,
        )

    def fake_popular(api_key: str, page: int) -> httpx.Response:
        return _page_response([_movie_result(100, "P100")])

    monkeypatch.setattr(ingest_mod, "fetch_discover_movie_page_sync", fake_discover)
    monkeypatch.setattr(ingest_mod, "fetch_popular_page_sync", fake_popular)

    movies = ingest_mod._collect_movies("key", genre_map, target=5)
    assert len(movies) == 5
    assert [m["tmdb_id"] for m in movies[:4]] == [1, 2, 3, 4]
    assert movies[4]["tmdb_id"] == 100


def test_reset_collection_wipes_and_recreates(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(store_mod.settings, "rag_chroma_path", str(tmp_path / "chroma"))
    monkeypatch.setattr(store_mod.settings, "rag_collection", "movies_test")
    store_mod._client = None

    store_mod.upsert_movies(
        ids=["1"],
        documents=["Doc"],
        metadatas=[{"tmdb_id": 1, "title": "A", "year": "", "poster_path": "", "rating": 0.0}],
        embeddings=[[0.1, 0.2, 0.3]],
    )
    assert store_mod.count_movies() == 1

    store_mod.reset_collection()
    assert store_mod.count_movies() == 0

    store_mod.upsert_movies(
        ids=["2"],
        documents=["Doc2"],
        metadatas=[{"tmdb_id": 2, "title": "B", "year": "", "poster_path": "", "rating": 0.0}],
        embeddings=[[0.3, 0.2, 0.1]],
    )
    assert store_mod.count_movies() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_rag_ingest.py -v`

Expected: FAIL (missing `fetch_discover_movie_page_sync` / `reset_collection` / old collector behavior)

- [ ] **Step 3: Implement client, store reset, mix collector**

`app/movies/client.py` — add next to popular helpers:

```python
def fetch_discover_movie_page_sync(
    api_key: str,
    page: int,
    *,
    vote_count_gte: int = 200,
) -> httpx.Response:
    with httpx.Client(timeout=TMDB_TIMEOUT) as client:
        return client.get(
            f"{TMDB_BASE_URL}/discover/movie",
            params={
                "api_key": api_key,
                "language": "en-US",
                "include_adult": "false",
                "include_video": "false",
                "sort_by": "vote_average.desc",
                "vote_count.gte": vote_count_gte,
                "page": page,
            },
        )


async def fetch_discover_movie_page(
    api_key: str,
    page: int,
    *,
    vote_count_gte: int = 200,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=TMDB_TIMEOUT) as client:
        return await client.get(
            f"{TMDB_BASE_URL}/discover/movie",
            params={
                "api_key": api_key,
                "language": "en-US",
                "include_adult": "false",
                "include_video": "false",
                "sort_by": "vote_average.desc",
                "vote_count.gte": vote_count_gte,
                "page": page,
            },
        )
```

`app/rag/store.py` — add:

```python
def reset_collection() -> None:
    client = _get_client()
    name = settings.rag_collection
    try:
        client.delete_collection(name=name)
    except Exception:
        # Collection may not exist yet
        pass
    client.get_or_create_collection(name=name)
```

Prefer catching Chroma’s not-found error if the installed chromadb exposes a specific exception; otherwise broad `Exception` is acceptable for “already missing”.

`app/rag/ingest.py` — update imports and replace `_collect_movies`:

```python
from math import ceil

from app.movies.client import (
    _map_rating,
    _map_year,
    fetch_discover_movie_page_sync,
    fetch_genre_list_sync,
    fetch_popular_page_sync,
    map_genre_ids,
)

DISCOVER_SHARE = 0.7
DISCOVER_VOTE_COUNT_GTE = 200


def _append_from_results(
    results: list[dict[str, Any]],
    *,
    movies: list[dict[str, Any]],
    seen_ids: set[int],
    genre_map: dict[int, str],
    limit: int,
) -> None:
    for result in results:
        if len(movies) >= limit:
            return
        movie_id = result.get("id")
        if movie_id is None or movie_id in seen_ids:
            continue
        overview = (result.get("overview") or "").strip()
        if not overview:
            continue
        seen_ids.add(movie_id)
        movies.append(
            {
                "tmdb_id": movie_id,
                "title": result.get("title") or "Unknown",
                "year": _map_year(result.get("release_date")),
                "poster_path": result.get("poster_path"),
                "rating": _map_rating(result.get("vote_average")),
                "overview": overview,
                "genre_names": map_genre_ids(
                    result.get("genre_ids") or [], genre_map
                ),
            }
        )


def _paginate(
    fetch_page,
    api_key: str,
    *,
    movies: list[dict[str, Any]],
    seen_ids: set[int],
    genre_map: dict[int, str],
    limit: int,
) -> None:
    page = 1
    while len(movies) < limit:
        response = fetch_page(api_key, page)
        if response.status_code != 200:
            raise RuntimeError(
                f"TMDB page {page} failed: HTTP {response.status_code}"
            )
        payload = response.json()
        results = payload.get("results", [])
        if not results:
            break
        before = len(movies)
        _append_from_results(
            results,
            movies=movies,
            seen_ids=seen_ids,
            genre_map=genre_map,
            limit=limit,
        )
        if len(movies) == before:
            # All results were dupes/empty — still advance; stop at last page
            pass
        if page >= payload.get("total_pages", page):
            break
        page += 1
        time.sleep(PAGE_SLEEP_SECONDS)


def _collect_movies(
    api_key: str,
    genre_map: dict[int, str],
    target: int,
) -> list[dict[str, Any]]:
    movies: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    discover_target = min(target, ceil(DISCOVER_SHARE * target))

    def discover_fetch(key: str, page: int) -> httpx.Response:
        return fetch_discover_movie_page_sync(
            key, page, vote_count_gte=DISCOVER_VOTE_COUNT_GTE
        )

    _paginate(
        discover_fetch,
        api_key,
        movies=movies,
        seen_ids=seen_ids,
        genre_map=genre_map,
        limit=discover_target,
    )
    _paginate(
        fetch_popular_page_sync,
        api_key,
        movies=movies,
        seen_ids=seen_ids,
        genre_map=genre_map,
        limit=target,
    )
    return movies
```

Add `import httpx` at top of `ingest.py` if used in type/annotation of nested function return (or omit annotation).

Do **not** call `reset_collection` in this task yet unless you also update `run_ingest` in Task 2 in the same commit — prefer leaving `run_ingest` wiring for Task 2. Collector + helpers only; `run_ingest` still uses `_collect_movies` but error message can stay until Task 2.

Actually: `_collect_movies` signature/behavior changes in place, so `run_ingest` will already use the mix without reset until Task 2. That is OK for intermediate state; Task 2 adds reset + README.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_rag_ingest.py -q`

Expected: all PASS

Note: `test_reset_collection_wipes_and_recreates` needs a real embedding dimension Chroma accepts — if Chroma complains about embedding length, use a vector of length 384 or whatever nomic uses; for a wipe test, prefer creating via collection.add with matching dim. If upsert fails due to dim, use:

```python
collection = store_mod.get_collection()
collection.add(ids=["1"], documents=["Doc"], metadatas=[...], embeddings=[[0.0] * 3])
```

Adjust embedding length if chromadb validates against existing collection space — for a fresh tmp path, short vectors are usually fine.

- [ ] **Step 5: Commit**

```bash
git add app/movies/client.py app/rag/store.py app/rag/ingest.py tests/test_rag_ingest.py
git commit -m "feat: collect RAG movies from discover+popular mix"
```

---

### Task 2: Wire full rebuild into run_ingest + README

**Files:**
- Modify: `app/rag/ingest.py` (`run_ingest`)
- Modify: `README.md`
- Modify: `tests/test_rag_ingest.py` (add one test that `run_ingest` calls reset)

**Interfaces:**
- Consumes: `reset_collection` from Task 1, `_collect_movies` mix
- Produces: `run_ingest` always resets before indexing; README documents mix + rebuild

- [ ] **Step 1: Write failing test for reset-on-ingest**

Append to `tests/test_rag_ingest.py`:

```python
def test_run_ingest_resets_collection_before_upsert(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(ingest_mod.settings, "tmdb_api_key", "key")
    monkeypatch.setattr(ingest_mod, "ping_ollama_sync", lambda: True)
    monkeypatch.setattr(
        ingest_mod,
        "fetch_genre_list_sync",
        lambda key: httpx.Response(200, json={"genres": [{"id": 18, "name": "Drama"}]}),
    )
    monkeypatch.setattr(
        ingest_mod,
        "_collect_movies",
        lambda api_key, genre_map, target: [
            {
                "tmdb_id": 1,
                "title": "One",
                "year": "2010",
                "poster_path": "/x.jpg",
                "rating": 8.0,
                "overview": "Plot.",
                "genre_names": ["Drama"],
            }
        ],
    )
    monkeypatch.setattr(ingest_mod, "embed_texts", lambda docs: [[0.1, 0.2, 0.3] for _ in docs])

    def fake_reset() -> None:
        calls.append("reset")

    def fake_upsert(*args, **kwargs) -> None:
        calls.append("upsert")

    monkeypatch.setattr(ingest_mod, "reset_collection", fake_reset)
    monkeypatch.setattr(ingest_mod, "upsert_movies", fake_upsert)

    indexed = ingest_mod.run_ingest()
    assert indexed == 1
    assert calls[0] == "reset"
    assert "upsert" in calls
```

Ensure `ingest.py` imports `reset_collection` from `app.rag.store` (will fail until Step 3).

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_rag_ingest.py::test_run_ingest_resets_collection_before_upsert -v`

Expected: FAIL (`reset_collection` not used / ImportError)

- [ ] **Step 3: Wire run_ingest + README**

In `app/rag/ingest.py`:

```python
from app.rag.store import reset_collection, upsert_movies
```

In `run_ingest`, after genre_map is built and before/after collect — **reset before upsert**, ideally after successful collect so a failed TMDB fetch does not wipe the index:

```python
    movies = _collect_movies(api_key, genre_map, settings.rag_movie_target)
    if not movies:
        raise RuntimeError("No movies collected from TMDB discover/popular pages")

    reset_collection()

    indexed = 0
    for start in range(0, len(movies), BATCH_SIZE):
        ...
```

Update the empty-collection error string as above.

`README.md` — replace the ingest blurb (~lines 63–72) with:

```markdown
### 2. Build the movie index

Requires `TMDB_API_KEY` in `.env` and a reachable Ollama embed endpoint:

```bash
source .venv/bin/activate
python -m app.rag.ingest
```

This **rebuilds** `data/chroma/` from a mix of ~70% well-rated TMDB discover movies (`vote_count ≥ 200`) and ~30% popular titles (~`RAG_MOVIE_TARGET`, default 5000). Re-running wipes the previous collection and re-indexes.

Check readiness: [http://127.0.0.1:8000/rag/status](http://127.0.0.1:8000/rag/status) — `index_ready` should be `true` when ingest finished.
```

(Keep surrounding README structure; only update this subsection. If uncommitted README edits already exist for other reasons, merge carefully.)

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_rag_ingest.py -q`

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/rag/ingest.py README.md tests/test_rag_ingest.py
git commit -m "feat: rebuild Chroma on ingest with discover/popular mix docs"
```

- [ ] **Step 6: Operator note (manual, not committed)**

After code lands, run locally:

```bash
source .venv/bin/activate
python -m app.rag.ingest
```

Expect several minutes; then spot-check year distribution or recommend quality.

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| 70/30 discover + popular | Task 1 |
| Discover params + vote_count 200 | Task 1 |
| Dedupe by tmdb_id | Task 1 |
| Skip empty overview | Task 1 |
| reset_collection / full rebuild | Task 1 (fn) + Task 2 (wire) |
| README operator docs | Task 2 |
| No recommend schema changes | N/A (unchanged) |
| Out of scope B/C | Not implemented |
