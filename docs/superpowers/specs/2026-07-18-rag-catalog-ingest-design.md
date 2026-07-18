# Better movie catalog ingest (70/30 mix + rebuild) — Design

## Goal

Replace the TMDB **popular-only** ingest so the Chroma index is mostly **well-regarded films** (high vote average with enough votes), with a smaller slice of **current popular** titles. Each ingest **fully rebuilds** the collection so old popular-heavy rows do not linger.

This is slice **A** of the broader RAG quality work (diversity across runs and mood-query quality are out of scope here).

## Problem

Current index (~5k from `/movie/popular`) is skewed to recent/upcoming titles (hundreds from 2025–2026). Retrieval then surfaces weak or unfamiliar candidates, so recommendations feel repetitive and low-quality even when the pipeline is otherwise fine.

## Decisions

| Topic | Choice |
|-------|--------|
| Catalog mix | ~70% discover (rated), ~30% popular |
| Rebuild | Wipe Chroma collection, then re-index |
| Target size | Keep `RAG_MOVIE_TARGET` (default 5000) |
| Language | `en-US` for discover (align with English overviews) |

## Out of scope

- Recommendation diversity between runs (session exclude / MMR)
- Richer mood query / larger fetch_k / prompt changes
- Genre-balanced or decade-balanced ingest
- Changing recommend runtime behavior beyond what a better index implies

## Ingest algorithm

1. **Reset** the movies collection (delete + recreate under the same name/path).
2. Fetch genre list (unchanged).
3. Collect movies until `target = settings.rag_movie_target` unique ids with non-empty overview:
   - **Discover quota:** `ceil(0.7 * target)` from `GET /3/discover/movie`  
     Params: `language=en-US`, `include_adult=false`, `include_video=false`, `sort_by=vote_average.desc`, `vote_count.gte=200`, paginate.
   - **Popular fill:** remaining slots from `GET /3/movie/popular` (existing helper), skip ids already collected.
4. Embed + upsert in batches (unchanged document/metadata shape).

If discover pages run out before the quota, continue filling from popular. If total unique movies with overview still fall short of target, index what was collected and log the count (same spirit as today).

### Constants (defaults)

- Discover share: `0.7`
- `vote_count.gte`: `200` (TMDB top-rated style threshold)
- Keep existing `BATCH_SIZE` / page sleep

Optional env overrides are **not** required for v1; hardcode share/threshold in ingest unless already following a config pattern for similar knobs.

## Code changes

| Area | Change |
|------|--------|
| `app/movies/client.py` | Add sync (+ async if consistent) `fetch_discover_movie_page` → `/discover/movie` with the params above |
| `app/rag/store.py` | `reset_collection()` — delete collection by name, then `get_or_create_collection` |
| `app/rag/ingest.py` | Call reset first; replace `_collect_movies` with mix collector; update error strings |
| `README.md` | Document mix + that ingest rebuilds the index |
| Tests | Unit-test collector logic with mocked page responses (quota split + dedupe); test `reset_collection` if feasible with temp chroma path |

## Operator steps

After merge/deploy of code:

```bash
python -m app.rag.ingest
```

Expect a full re-embed (minutes depending on Ollama). `/rag/status` should show `index_ready` and a count near target.

## Success criteria

- Post-ingest year distribution is **not** dominated by 2025–2026 the way popular-only was.
- Sample retrieval for a mood query surfaces recognizable / higher-voted titles more often.
- Re-running ingest replaces the index (count ≈ target, not target + old leftovers).

## Compatibility

- Document text and metadata schema unchanged → no recommend code changes required for this slice.
- Existing popular fetch helpers remain for the 30% fill and any other callers.
