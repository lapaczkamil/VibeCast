# Seed Tracks Recommend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users seed movie recommendations with up to 5 selected Spotify tracks (Listening + search), falling back to now playing when none are selected.

**Architecture:** Extend `POST /recommend` with an optional `tracks` body; when present, build mood only from those tracks; when empty, use currently playing or return 400. Add `GET /spotify/search`. SPA keeps `seeds` in `App`, toggles in Listening (including search), chips on `RecommendStage`.

**Tech Stack:** FastAPI, Pydantic, httpx/respx, React 19, TypeScript, Vite.

## Global Constraints

- Max **5** unique seeds by Spotify track `id`.
- Empty seeds → mood from **now playing** only; if nothing playing → **400** `"Select at least one track or start playing music"`.
- With seeds → do **not** auto-merge recent/top/artists.
- No new OAuth scopes; no seed persistence across reload; clear seeds on logout.
- Spec: `docs/superpowers/specs/2026-07-16-seed-tracks-recommend-design.md`
- Existing happy-path recommend tests mock currently-playing **204** and relied on recent/top — they **must** be updated to POST with `tracks` or mock a playing track.

---

## File structure

| File | Responsibility |
|------|----------------|
| `app/rag/schemas.py` | `RecommendTrackSeed`, `RecommendRequest` |
| `app/rag/recommend.py` | Dedup seeds, mood from seeds / now-playing fallback, `recommend_for_user(request)` |
| `app/rag/routes.py` | Accept body on `POST /recommend` |
| `app/spotify/client.py` | `fetch_search`, `map_search_tracks` |
| `app/spotify/schemas.py` | `TrackSearchItem`, `TrackSearchResponse` |
| `app/spotify/routes.py` | `GET /spotify/search` |
| `tests/test_rag_recommend.py` | Seed / fallback / 400 / 422 + update old happy paths |
| `tests/test_spotify_search.py` | Search auth + happy path |
| `frontend/src/types.ts` | `SeedTrack`, search types; extend recommend API types |
| `frontend/src/api.ts` | `requestRecommendations(tracks)`, `searchSpotifyTracks` |
| `frontend/src/lib/seeds.ts` | Pure `toggleSeed` / dedupe helpers (optional but preferred) |
| `frontend/src/components/ListeningDrawer.tsx` | Selectable rows + search + footer |
| `frontend/src/components/TrackList.tsx` / `NowPlaying.tsx` | Selection props |
| `frontend/src/components/RecommendStage.tsx` | Chips + enable rules + pass tracks |
| `frontend/src/App.tsx` | Own `seeds` state |
| `frontend/src/styles.css` | Seed chips, selectable rows, drawer footer |

---

### Task 1: Recommend request body + mood rules

**Files:**
- Modify: `app/rag/schemas.py`
- Modify: `app/rag/recommend.py`
- Modify: `app/rag/routes.py`
- Modify: `tests/test_rag_recommend.py`

**Interfaces:**
- Produces:
  ```python
  class RecommendTrackSeed(BaseModel):
      id: str
      name: str
      artists: list[str]

  class RecommendRequest(BaseModel):
      tracks: list[RecommendTrackSeed] = []

  async def recommend_for_user(request: RecommendRequest | None = None) -> RecommendResponse
  MAX_SEEDS = 5
  ```
- Mood from seeds: `build_mood_query` / new helper with lines `"{name} by {artists}"` under prefix `Selected tracks:`.
- Empty seeds: only currently playing (`Now: …`); no recent/top/artists fetches when seeds provided; when seeds empty, only fetch currently playing (skip recent/top/artists).

- [ ] **Step 1: Write failing tests**

Add to `tests/test_rag_recommend.py` (keep imports/helpers):

```python
def test_recommend_with_seed_tracks_skips_listening_history(monkeypatch):
    oauth.set_tokens(TOKENS)
    # Do NOT mock recent/top — if called, respx will fail / unmocked error
    respx.get("https://api.spotify.com/v1/me/player/currently-playing").mock(
        return_value=Response(204)
    )
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    captured: list[str] = []

    def fake_embed(texts):
        captured.extend(texts)
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr("app.rag.recommend.embed_texts", fake_embed)
    monkeypatch.setattr(
        "app.rag.recommend.query_movies",
        lambda emb, k: (["doc"], CANDIDATE_METADATAS[:1]),
    )
    monkeypatch.setattr(
        "app.rag.recommend.chat_json",
        lambda prompt: json.dumps(
            {
                "mood_summary": "Seeded",
                "items": [{"tmdb_id": 550, "title": "Fight Club", "reason": "x"}],
            }
        ),
    )

    with respx.mock:  # or use @respx.mock on the test
        response = client.post(
            "/recommend",
            json={
                "tracks": [
                    {"id": "s1", "name": "Seed Song", "artists": ["Seed Artist"]}
                ]
            },
        )
    assert response.status_code == 200
    assert "Seed Song" in captured[0]
    assert "Recent1" not in captured[0]


def test_recommend_empty_tracks_no_now_playing_400(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    with respx.mock:
        respx.get("https://api.spotify.com/v1/me/player/currently-playing").mock(
            return_value=Response(204)
        )
        response = client.post("/recommend", json={"tracks": []})
    assert response.status_code == 400
    assert "select" in response.json()["detail"].lower()


def test_recommend_more_than_five_seeds_422(monkeypatch):
    oauth.set_tokens(TOKENS)
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 100)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: True)
    tracks = [
        {"id": f"t{i}", "name": f"S{i}", "artists": ["A"]} for i in range(6)
    ]
    response = client.post("/recommend", json={"tracks": tracks})
    assert response.status_code == 422
```

Update `test_recommend_happy_path`, `test_recommend_drops_unknown_tmdb_ids`, `test_recommend_parse_failure_502` to POST with at least one seed track in JSON body (so they no longer need full `_mock_spotify_context` for recent/top — can drop those mocks or keep unused).

- [ ] **Step 2: Run tests — expect FAIL**

Run: `.venv/bin/pytest tests/test_rag_recommend.py -v`  
Expected: new tests fail (422/400/body ignored).

- [ ] **Step 3: Implement schemas + recommend + route**

`app/rag/schemas.py` — add models above.

`app/rag/recommend.py` — sketch:

```python
MAX_SEEDS = 5

def _normalize_seeds(tracks: list[RecommendTrackSeed]) -> list[RecommendTrackSeed]:
    seen: set[str] = set()
    out: list[RecommendTrackSeed] = []
    for t in tracks:
        if t.id in seen:
            continue
        seen.add(t.id)
        out.append(t)
    return out

async def recommend_for_user(request: RecommendRequest | None = None) -> RecommendResponse:
    request = request or RecommendRequest()
    seeds = _normalize_seeds(request.tracks)
    if len(request.tracks) > MAX_SEEDS:
        raise HTTPException(status_code=422, detail="At most 5 tracks allowed")
    # Prefer validating length before normalize, or after normalize:
    # Spec: reject >5 — validate on raw len(request.tracks) > 5 → 422

    if seeds:
        lines = [_track_line(t.name, t.artists) for t in seeds]
        mood_query = "Selected tracks: " + ", ".join(lines)
    else:
        now_playing_line = await _now_playing_line_only()
        if not now_playing_line:
            raise HTTPException(
                status_code=400,
                detail="Select at least one track or start playing music",
            )
        mood_query = now_playing_line
    # then embed / query / chat as today
```

`_now_playing_line_only`: only call currently-playing (reuse mapping from `_gather_spotify_lines`).

`app/rag/routes.py`:

```python
async def recommend(body: RecommendRequest | None = None) -> RecommendResponse:
    ...
    return await recommend_for_user(body or RecommendRequest())
```

Use `body: RecommendRequest = RecommendRequest()` so empty POST still works.

- [ ] **Step 4: Run tests — expect PASS**

Run: `.venv/bin/pytest tests/test_rag_recommend.py -v`  
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/rag/schemas.py app/rag/recommend.py app/rag/routes.py tests/test_rag_recommend.py
git commit -m "feat: accept seed tracks on recommend endpoint"
```

---

### Task 2: Spotify track search endpoint

**Files:**
- Modify: `app/spotify/client.py`
- Modify: `app/spotify/schemas.py`
- Modify: `app/spotify/routes.py`
- Create: `tests/test_spotify_search.py`

**Interfaces:**
- `SEARCH_URL = "https://api.spotify.com/v1/search"`
- `async def fetch_search(access_token: str, q: str, limit: int = 10) -> httpx.Response`
- `def map_search_tracks(payload: dict) -> list[TrackSearchItem]`
- Route: `GET /spotify/search?q=&limit=10` → `TrackSearchResponse`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_spotify_search.py
import respx
from fastapi.testclient import TestClient
from httpx import Response
from app.main import app
from app.spotify import oauth
from app.spotify.oauth import TokenSet

client = TestClient(app)
TOKENS = TokenSet(access_token="access-abc", refresh_token="refresh-xyz", expires_at=None)

def setup_function():
    oauth.clear_tokens()
    oauth.clear_pending_state()

def test_search_unauthorized():
    r = client.get("/spotify/search", params={"q": "radiohead"})
    assert r.status_code == 401

@respx.mock
def test_search_happy_path():
    oauth.set_tokens(TOKENS)
    respx.get("https://api.spotify.com/v1/search").mock(
        return_value=Response(
            200,
            json={
                "tracks": {
                    "items": [
                        {
                            "id": "abc",
                            "name": "Creep",
                            "artists": [{"name": "Radiohead"}],
                            "album": {
                                "name": "Pablo Honey",
                                "images": [{"url": "https://img/x"}],
                            },
                            "external_urls": {"spotify": "https://open.spotify.com/track/abc"},
                        }
                    ]
                }
            },
        )
    )
    r = client.get("/spotify/search", params={"q": "creep", "limit": 10})
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["id"] == "abc"
    assert item["name"] == "Creep"
    assert item["artists"] == ["Radiohead"]

def test_search_blank_query_422():
    oauth.set_tokens(TOKENS)
    r = client.get("/spotify/search", params={"q": "  "})
    assert r.status_code == 422
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/pytest tests/test_spotify_search.py -v`  
Expected: 404 / fail.

- [ ] **Step 3: Implement client + route**

```python
# client
SEARCH_URL = "https://api.spotify.com/v1/search"

async def fetch_search(access_token: str, q: str, limit: int = 10) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        return await client.get(
            SEARCH_URL,
            params={"q": q, "type": "track", "limit": limit},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )

def map_search_tracks(payload: dict) -> list[TrackSearchItem]:
    items = []
    for track in payload.get("tracks", {}).get("items", []) or []:
        if not track or not track.get("id"):
            continue
        album = track.get("album") or {}
        items.append(
            TrackSearchItem(
                id=track["id"],
                name=track["name"],
                artists=[a["name"] for a in track.get("artists", [])],
                album=album.get("name") or "",
                spotify_url=track["external_urls"]["spotify"],
                image_url=_first_image_url(album.get("images")),
            )
        )
    return items
```

Route pattern mirrors other Spotify GETs with `_authed_spotify`.

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/pytest tests/test_spotify_search.py tests/test_rag_recommend.py -v`

- [ ] **Step 5: Commit**

```bash
git add app/spotify/client.py app/spotify/schemas.py app/spotify/routes.py tests/test_spotify_search.py
git commit -m "feat: add Spotify track search endpoint"
```

---

### Task 3: Frontend seeds — Listening + stage chips

**Files:**
- Modify: `frontend/src/types.ts`, `frontend/src/api.ts`
- Create: `frontend/src/lib/seeds.ts` (pure toggle helper)
- Modify: `frontend/src/components/NowPlaying.tsx`, `TrackList.tsx`, `ListeningDrawer.tsx`, `RecommendStage.tsx`, `App.tsx`, `styles.css`

**Interfaces:**
```ts
export type SeedTrack = {
  id: string;
  name: string;
  artists: string[];
};

export const MAX_SEEDS = 5;

export function toggleSeed(
  seeds: SeedTrack[],
  track: SeedTrack,
): { seeds: SeedTrack[]; rejected: boolean };
```

`requestRecommendations(tracks: SeedTrack[]): Promise<RecommendResponse>` — POST JSON `{ tracks }` (map `id` field).

`searchSpotifyTracks(q: string, limit = 10)`.

- [ ] **Step 1: Types + api + seed helper**

Implement `toggleSeed`: if id present → remove; else if `seeds.length >= MAX_SEEDS` → `{ seeds, rejected: true }`; else append.

Update `requestRecommendations` to accept tracks and send body; handle **400** with server detail message.

- [ ] **Step 2: Selectable lists + ListeningDrawer**

Extend `RecentTrackList` / `TopTrackList` / `NowPlaying` with optional:

```ts
selectedIds: Set<string> | string[];
onToggle: (track: SeedTrack) => void;
disabledAdd: boolean; // at limit and not selected
```

Checkbox (or `aria-pressed` button) per row. For NowPlaying, only when `data.track` exists.

`ListeningDrawer`: receive `seeds`, `onToggleSeed`, `onClearSeeds`; render search input (debounce ~300ms or submit-on-Enter); call `searchSpotifyTracks`; sticky footer `Seeds: N/5` + Clear.

- [ ] **Step 3: App state + RecommendStage**

`App`:
```ts
const [seeds, setSeeds] = useState<SeedTrack[]>([]);
const handleToggleSeed = (track: SeedTrack) => {
  const { seeds: next, rejected } = toggleSeed(seeds, track);
  setSeeds(next);
  // optional: setLimitHint if rejected
};
// clear on logout
```

Pass seeds into Listening + RecommendStage.

`RecommendStage` props:
```ts
seeds: SeedTrack[];
hasNowPlaying: boolean;
onRemoveSeed: (id: string) => void;
```

- Chips with ×.
- `canRun = ragReady && (seeds.length > 0 || hasNowPlaying)`.
- Hint when `!canRun` for seed reason.
- `requestRecommendations(seeds)` on recommend / match again.

`hasNowPlaying`: from `currentlyPlaying.status === "ok" && currentlyPlaying.data?.track != null` (is_playing optional — if track present treat as usable per API which uses currently-playing item).

- [ ] **Step 4: CSS**

Seed chips, checkbox row alignment, sticky `.listening-footer`, search results in drawer.

- [ ] **Step 5: Build + backend tests**

```bash
cd frontend && npm run build && npm run lint
cd .. && .venv/bin/pytest -q
```

Expected: build OK; all tests pass.

- [ ] **Step 6: Manual smoke**

Login → Listening → select tracks → chips on stage → Recommend; clear; search add; empty + no play → disabled; play music + no seeds → enabled.

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat(ui): select seed tracks for recommendations"
```

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| POST body + mood from seeds | 1 |
| Empty → now playing / 400 | 1 |
| Max 5 / 422 | 1 |
| GET /spotify/search | 2 |
| Listening checkboxes + search + footer | 3 |
| Stage chips + CTA rules | 3 |
| Clear on logout | 3 |
| Tests backend | 1–2 |
| No new scopes / no persistence | Global |

No placeholders. Existing recommend happy paths must send seeds after Task 1.
