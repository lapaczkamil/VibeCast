# ReccoBeats audio features in movie recommend

**Date:** 2026-07-18  
**Status:** Approved for planning  
**Scope:** Backend enrichment of the recommend pipeline using ReccoBeats track audio features

## Problem

`POST /recommend` builds a mood query mostly from track title + artist. Spotify’s official audio-features API is unavailable for new apps, so the RAG path lacks objective musical descriptors (energy, valence, tempo, etc.). Film retrieval and LLM reasons therefore underuse the actual sound of the seed track.

## Goals

- Fetch audio features for the selected Spotify track via ReccoBeats.
- Enrich `mood_query` with a natural-language audio profile so Ollama embeddings retrieve better Chroma candidates.
- Rerank enlarged Chroma results using feature→genre affinity before the LLM picks 3–5 films.
- Soft-fail: if ReccoBeats is down/missing data, recommend behaves as today.

## Non-goals (v1)

- Frontend UI for audio features
- Re-ingesting Chroma with mood tags on movies
- Public diagnostic ReccoBeats endpoints
- Multi-seed batching (product remains `MAX_SEEDS = 1`)
- Hard dependency on ReccoBeats for recommend success

## Decisions

| Topic | Choice |
|-------|--------|
| Integration depth | Enrich mood query **and** post-Chroma rerank |
| Failure mode | Soft-fail (log + continue without features) |
| Package layout | New `app/reccobeats/` module, wired from `recommend.py` |
| Auth | No API key required for public ReccoBeats docs; configurable base URL |
| FE contract | Unchanged (`RecommendRequest` / `RecommendResponse`) |

## Architecture

```
app/reccobeats/
  client.py    # HTTP GET /v1/audio-features?ids=
  schemas.py   # AudioFeatures pydantic model
  mood.py      # features → natural-language mood lines
  rerank.py    # score Chroma candidates by genre affinity
```

Config (`app/config.py`):

- `reccobeats_base_url` default `https://api.reccobeats.com`
- `reccobeats_timeout_seconds` default `4.0`

In-memory cache of features keyed by Spotify track id (TTL ~1 hour). Separate httpx client — does **not** share Spotify upstream circuit breaker.

### Flow

1. Normalize seed (`MAX_SEEDS = 1`).
2. Build base mood line: `Selected tracks: {name} by {artists}`.
3. Call ReccoBeats with Spotify track id.
4. On success: append audio-profile lines from `mood.py` to `mood_query`.
5. Embed `mood_query` via Ollama; query Chroma with enlarged `n_results` (e.g. 16).
6. `rerank.py` sorts candidates; keep top 8 for the LLM prompt (same as today’s effective list size).
7. Existing LLM JSON pick + TMDB rating enrich unchanged.

## Data: ReccoBeats

**Endpoint:** `GET {base}/v1/audio-features?ids={spotify_track_id}`  
**Headers:** `Accept: application/json`

Relevant fields (0–1 unless noted): `acousticness`, `danceability`, `energy`, `instrumentalness`, `liveness`, `speechiness`, `valence`, `tempo` (BPM), `loudness` (dB), `key`, `mode`.

Response shape: `{ "content": [ { ...features } ] }` (or empty / 404 when unknown).

## Mood enrichment

Thresholded descriptors appended as concise English (stable for embeddings), e.g.:

```text
Selected tracks: Song by Artist
Audio profile: high energy, dark/low valence, moderate tempo (~92 BPM), low danceability, mostly acoustic
```

Example buckets (implementation may tune numbers; keep documented in code):

| Feature | Low | Mid | High |
|---------|-----|-----|------|
| energy | calm / subdued | balanced energy | intense / high-energy |
| valence | dark / melancholic | emotionally mixed | bright / uplifting |
| danceability | introspective | moderately rhythmic | danceable |
| acousticness | electronic / produced | mixed production | acoustic / organic |
| instrumentalness | vocal-led | — | instrumental |
| tempo | slow (&lt;90) | mid (90–120) | fast (&gt;120) |

## Rerank

- Input: Chroma documents + metadatas (must include genre names if present in metadata; fall back to parsing `Genres:` from document text when needed).
- Score = Chroma order bias (or distance if exposed) + genre affinity boost from audio profile.
- Example affinities (non-exhaustive; code owns the table):
  - high energy → Action, Adventure, Thriller, Science Fiction
  - low valence → Drama, Horror, Crime, War
  - high valence → Comedy, Romance, Family, Animation
  - high acousticness → Documentary, Drama, Music, History
  - high danceability → Music, Comedy, Romance
- Output: reordered list truncated to `RAG_TOP_K` (8) for the LLM.

## Error handling

| Case | Behavior |
|------|----------|
| Timeout / network error | Soft-fail |
| HTTP 4xx/5xx / empty content | Soft-fail |
| Invalid/missing track id | Skip ReccoBeats call |
| Soft-fail | Recommend with title+artist mood only; no user-facing error |

Log at warning level with track id and status; never trip Spotify rate-limit circuit.

## Testing

- Unit: `mood.py` descriptor strings for fixture feature vectors
- Unit: `rerank.py` ordering with known genre metadata
- Client: httpx mock — 200 with content, 404, timeout
- Recommend integration (mocked ReccoBeats + Ollama/Chroma as in existing tests): features present in mood path when ReccoBeats succeeds; recommend still succeeds when ReccoBeats fails

## Rollout

1. Implement `app/reccobeats/` + config
2. Wire into `recommend_for_user`
3. Add tests
4. Manual check: seed a known Spotify track, confirm logs/features and improved candidate mix

No frontend deploy required.
