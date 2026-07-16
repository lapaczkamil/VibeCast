# Seed tracks for movie recommendations — Design

**Date:** 2026-07-16  
**Branch:** `feat/ollama-rag`  
**Scope:** Backend + frontend — user-selected Spotify tracks drive `POST /recommend` mood; Listening multi-select + Spotify search; stage seed chips

## Goal

Let users choose which songs seed movie recommendations (from Listening lists and Spotify search), instead of always using the full auto Spotify context. Keep the immersive recommend-first UI.

## Decisions (locked)

| Topic | Choice |
|--------|--------|
| Track sources | Listening lists **and** Spotify search |
| Empty selection | Use **now playing** only if something is playing; otherwise require ≥1 seed (Recommend disabled / API 400) |
| Selection UI | In **Listening** drawer (checkboxes + search); stage shows **chips** only |
| API shape | `POST /recommend` body with track descriptors; separate `GET /spotify/search` |
| Max seeds | **5** unique tracks by Spotify track `id` |
| Persistence | In-memory in SPA until logout; not persisted across reload |

## API

### `POST /recommend`

Optional JSON body:

```json
{
  "tracks": [
    { "id": "spotifyTrackId", "name": "Song", "artists": ["Artist"] }
  ]
}
```

Rules:

1. If `tracks` has 1–5 items (after dedupe by `id`): build `mood_query` **only** from those tracks (no recently played / top tracks / top artists / auto now-playing merge).
2. If `tracks` is missing or empty: fetch currently playing; if a track is present, mood = that track only; else **400** with detail like `Select at least one track or start playing music`.
3. Reject >5 tracks with **422**.
4. RAG / Ollama / Chroma pipeline unchanged after `mood_query` is built.

Schemas (Pydantic): `RecommendTrackSeed`, `RecommendRequest` (tracks default `[]`), existing `RecommendResponse`.

### `GET /spotify/search?q={query}&limit=10`

- Requires Spotify auth (same as other `/spotify/*` routes).
- Returns `{ "items": [ { "id", "name", "artists", "album", "spotify_url", "image_url"? } ] }`.
- Empty `q` → empty items (200) or 422 — prefer **422** for blank query.
- No new OAuth scopes required for Search with an existing user access token.

## Mood construction

- Selected / now-playing tracks → lines like `"{name} by {artists}"`, joined under a short prefix (e.g. `Selected tracks:` or `Now:`).
- Do **not** include top artists or recent lists when seeds or now-playing-only fallback is used.

## Frontend

### State (`App`)

- `seeds: SeedTrack[]` — `{ id, name, artists }` (album/url optional for display).
- `toggleSeed(track)` — add if under 5 and not present; remove if present; no-op add when at limit (show brief hint in Listening).
- `clearSeeds()`, `removeSeed(id)`.
- Clear seeds on logout.

### Listening drawer

- Now playing, recently played, top tracks: each row selectable (checkbox or whole-row toggle).
- New **Search Spotify** block: query input, results list with same toggle.
- Sticky footer: `Seeds: N/5` + **Clear** when N > 0.
- Top artists: display only (not selectable).

### Recommend stage

- Chip row above CTA for each seed (`Title — Artist`, × removes).
- Recommend enabled when: `seeds.length > 0` **or** (optional) client knows now playing is active — prefer enabling when seeds nonempty; when seeds empty, allow click and let API return 400 **or** disable when seeds empty and currentlyPlaying has no track. **Preferred:** disable CTA when `seeds.length === 0` and no now-playing track; enable when seeds or now-playing track exists.
- `requestRecommendations(seeds)` sends body `{ tracks: seeds }` (empty array when relying on now playing).

Pass `currentlyPlaying` (or a boolean `hasNowPlaying`) into `RecommendStage` for enable/disable.

## Out of scope

- Seeding by artist or playlist
- Persisting seeds across page reload / server session
- New Spotify OAuth scopes
- Changing RAG index or Ollama models

## Success criteria

1. User can pick up to 5 tracks from Listening + search; chips reflect selection on stage.
2. Recommend with seeds uses only those tracks for mood.
3. No seeds + music playing → recommend uses now playing.
4. No seeds + nothing playing → CTA disabled / API 400.
5. Existing RAG happy path still works with seeds or now-playing fallback.
6. Backend tests cover request body, empty fallback, 400, and search auth.

## Testing

- Unit/API: mood from tracks; empty → now playing; empty + no play → 400; >5 → 422; search unauthorized; search happy path (mocked Spotify).
- Manual: select in Listening, search add, chips remove, recommend, clear, logout clears seeds.
