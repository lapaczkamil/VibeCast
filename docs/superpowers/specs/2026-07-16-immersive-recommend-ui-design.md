# Immersive recommend-first UI — Design

**Date:** 2026-07-16  
**Branch:** `feat/ollama-rag`  
**Scope:** Frontend redesign only (no API changes)

## Goal

VibeCast’s logged-in experience must center on **movie recommendations from music mood**, not a long Spotify/TMDB dashboard. Secondary tools (listening context, movie search) stay available but off the main stage.

## Decisions (locked)

| Topic | Choice |
|--------|--------|
| Secondary content | Kept, hidden in drawers (“Listening”, “Search”) |
| Drawer pattern | Same sheet/drawer on desktop and mobile; opened by chrome buttons |
| Results presentation | Carousel — one movie at a time (arrows / swipe / keyboard) |
| Visual shell | **Immersive stage** — large poster, atmospheric background, slim top chrome |
| Landing | Brand + Spotify login only (no TMDB search while logged out) |
| Brand / palette | Keep existing teal/amber dark theme, Fraunces + Source Sans 3 |

## Information architecture

### Logged out
- Full-viewport composition: **VibeCast** (hero brand), one subtitle, one CTA (“Log in with Spotify”).
- Auth error / backend unreachable states unchanged in meaning; restyled to match.

### Logged in
- **Top chrome:** brand · Listening · Search · avatar + logout.
- **Main stage:** recommendation carousel (or idle / loading / error).
- **No** stacked Now playing / Recently played / Top tracks / Top artists / Movies sections on the main scroll.

### Drawers
- **Listening** (right sheet): Now playing, Recently played, Top tracks, Top artists — denser lists, scroll inside the sheet.
- **Search** (right sheet): existing TMDB `MoviesSearch`.
- Backdrop dim; close via ×, backdrop click, or Escape.
- Only one drawer open at a time.

## Main stage (Immersive)

### Idle (no results yet)
- Empty poster placeholder.
- Primary CTA: “Recommend movies”.
- RAG readiness warnings (index / Ollama) under the CTA — same conditions and copy intent as today’s `RecommendSection`.

### Loading
- Poster skeleton + “Matching movies to your vibe…”.
- Disable Recommend / Match again while request in flight.

### Success
- One film: large poster, title, year, short reason.
- Optional mood line (from `mood_summary`) above or below title if present — keep secondary to title.
- Dot indicators + prev/next controls.
- “Match again” re-runs `POST /recommend` and resets carousel index to 0.
- Soft atmospheric wash behind the stage (CSS from accent / poster-adjacent tones; no floating badges or promo chips on the poster).

### Empty / error
- Short message on stage + retry via the same primary action.

### Carousel interaction
- Prev/next buttons.
- Touch swipe.
- Arrow keys when the stage (or app) is focused and no drawer is open.

## Components (frontend)

| Piece | Role |
|--------|------|
| `App` | Auth flow; owns drawer open state; stops loading full dashboard into the main column |
| `AppChrome` / header | Brand, Listening, Search, profile/logout |
| `RecommendStage` | Idle / loading / carousel / error (evolves from `RecommendSection`) |
| `Drawer` | Shared sheet + backdrop |
| `ListeningDrawer` | Existing Spotify section components, compact layout |
| `SearchDrawer` | Wraps `MoviesSearch` |
| Existing lists | Reused inside Listening; not deleted |

Spotify data for Listening may still load after login (parallel fetches as today). Recommendation remains on-demand via existing recommend API.

## Out of scope

- Backend / RAG / Spotify / TMDB API changes.
- Bottom tab bar.
- Auto-recommend on login (stay button-driven unless a later change requests it).
- New visual brand system (palette/fonts stay).

## Success criteria

1. First logged-in viewport reads as a recommendation product, not a Spotify dashboard.
2. Listening and Search are reachable in one click without dominating the page.
3. Carousel shows one pick at a time with clear navigation.
4. Existing auth, logout, recommend, and search behaviors still work.
5. Usable on desktop and mobile (drawer + stage).

## Testing

- Manual: login → idle → recommend → carousel nav → Match again → drawers open/close → logout.
- Manual: recommend blocked when RAG not ready (warnings visible).
- Keep / adapt any existing frontend unit tests if present; no new backend tests required for this redesign.
