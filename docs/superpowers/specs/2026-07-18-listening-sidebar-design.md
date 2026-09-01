# Listening sidebar (built-in nav)

**Date:** 2026-07-18  
**Status:** Approved  
**Scope:** Frontend UX only — replace the Listening drawer with a permanent left rail so seed tracks are easier to drag onto the match slot.

## Problem

Tracks live in a modal **Listening** drawer opened from the top chrome. Dragging a seed onto the stage requires opening the drawer, then relying on soft/pass-through backdrop so drops hit the stage. That source of tracks feels awkward and makes the primary recommend flow harder than it should be.

## Goals

- Put Listening content in a **built-in left sidebar** always visible on desktop.
- Keep drag-and-drop seeding; remove drawer-specific drag workarounds.
- On mobile, keep the same panel but collapsible via a chrome toggle.
- Remove `ListeningDrawer` entirely.
- Leave `SearchDrawer` (movies / TMDB) as a top-bar drawer.

## Non-goals

- Backend / recommend / Spotify API changes.
- Redesigning Search drawer behavior or RecommendStage recommendation logic.
- New seed selection model (still one seed track, clear in footer).

## Layout

### Desktop (≥ ~900px)

```
[ AppChrome ]
[ ListeningPanel | RecommendStage ]
```

- Left panel width ~280–320px with its own vertical scroll.
- Stage keeps the match drop zone and recommendation carousel as today.
- No open/close state for the panel; it is always mounted and visible.

### Mobile (< ~900px)

- Panel hidden by default (off-canvas / slide-over from the left).
- Chrome **Listening** control toggles the panel (`aria-expanded`).
- On successful seed drop, auto-close the panel so the stage is visible.

### Chrome

| Viewport | Listening control | Search |
|----------|-------------------|--------|
| Desktop  | Hidden (panel always visible) | Unchanged drawer |
| Mobile   | Toggle panel + live dot when playing | Unchanged drawer |

## Components

### `ListeningPanel` (new)

Replaces `ListeningDrawer`. Same content sections, in order:

1. Spotify track search (Enter to search) — results draggable
2. Now playing — draggable
3. Recently played — draggable
4. Top tracks + time-range filters — draggable
5. Footer: selected seed name + Clear

Use `aside` with `aria-label="Listening"`. Reuse existing list/drag helpers (`TrackList`, `NowPlaying`, `seedDrag`, `DashboardSection`).

### Removals / cleanups

- Delete `ListeningDrawer` usage and file once panel lands.
- Remove `Drawer` softBackdrop / passThroughBackdrop usage tied to Listening drag (keep `Drawer` for Search if still needed).
- Drop `app--seed-dragging` / pass-through CSS only where it existed solely for drawer-over-stage drops; keep match-zone highlight while dragging if useful.
- Update RecommendStage / MatchDropZone copy from “Open Listening…” to “Drag a track from Listening” (or equivalent).

### `App.tsx` wiring

- Replace `drawer === "listening"` with:
  - Desktop: panel always present
  - Mobile: `listeningOpen` boolean for overlay panel
- `drawer` state remains only for `"search" | null` (or equivalent).

## Behavior

- **Drag MIME / drop:** unchanged (`SEED_DRAG_MIME`, `MatchDropZone`, single-seed replace on drop).
- **Search overlay:** when Search drawer is open, it stacks above panel + stage.
- **Section errors:** same loading / error / retry patterns inside the panel.
- **Breakpoint:** ~900px; match existing chrome responsive breakpoints if already close.

## Acceptance criteria

1. On a wide viewport, Now playing / recent / top / track search are visible without opening a drawer.
2. User can drag a track from the left panel onto the match slot and get the same seed behavior as today.
3. Listening drawer is gone; no soft pass-through backdrop required for drops.
4. On a narrow viewport, Listening starts closed; toggle opens it; successful drop closes it.
5. Search still opens from chrome as a drawer.
6. Drop-zone helper text no longer tells the user to open Listening.

## Implementation notes

Prefer extracting shared body markup from the current Listening drawer into `ListeningPanel` rather than rewriting list UI. Keep visual language (existing CSS variables / track rows) and adapt layout classes for a fixed rail vs. drawer sheet.
