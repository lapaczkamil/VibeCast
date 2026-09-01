# Listening Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Listening drawer with a permanent left `ListeningPanel` so seed tracks are always (desktop) or one-toggle (mobile) away from the match slot.

**Architecture:** Extract the Listening drawer body into `ListeningPanel` (`aside`). Desktop: fixed left rail beside `RecommendStage`. Mobile: off-canvas panel toggled from chrome; close on successful seed drop. Search stays a right `Drawer`. Remove Listening soft/pass-through backdrop hacks.

**Tech Stack:** React 19, TypeScript, Vite, existing CSS in `frontend/src/styles.css`.

## Global Constraints

- Frontend-only; do not change FastAPI / RAG / Spotify / TMDB routes.
- Desktop (≥ 900px): Listening panel always visible; no Listening chrome button.
- Mobile (< 900px): panel closed by default; chrome Listening toggles it; successful drop closes it.
- Remove `ListeningDrawer`; keep `SearchDrawer`.
- One seed track; Clear in panel footer; drag MIME unchanged.
- Copy: no “Open Listening…” — use “Drag a track from Listening” (or equivalent).
- Automated gate: `cd frontend && npm run build` (and `npm run lint` if clean). No frontend unit-test runner — do not add Vitest for this UI work; use the manual checklist.
- Spec: `docs/superpowers/specs/2026-07-18-listening-sidebar-design.md`

---

## File structure

| File | Responsibility |
|------|----------------|
| `frontend/src/components/ListeningPanel.tsx` | Built-in Listening rail: search, now playing, recent, top, seed footer |
| `frontend/src/components/ListeningDrawer.tsx` | Delete after panel lands |
| `frontend/src/components/AppChrome.tsx` | Listening toggle only on mobile; Search unchanged |
| `frontend/src/components/Drawer.tsx` | Drop `softBackdrop` / `passThroughBackdrop` (Search only needs plain drawer) |
| `frontend/src/App.tsx` | Stage row layout; `listeningOpen` + `drawer: null \| "search"` |
| `frontend/src/components/RecommendStage.tsx` | Idle lede copy update |
| `frontend/src/styles.css` | Stage workspace row, panel rail, mobile overlay, chrome toggle visibility |

Reuse unchanged: `MatchDropZone` (copy already OK), `TrackList`, `NowPlaying`, `DashboardSection`, `seedDrag`, `SearchDrawer`, `api.ts`, `types.ts`.

---

### Task 1: `ListeningPanel` component

**Files:**
- Create: `frontend/src/components/ListeningPanel.tsx`
- Keep (until Task 4): `frontend/src/components/ListeningDrawer.tsx`

**Interfaces:**
- Consumes: same Spotify section props as today’s drawer (without `open` / `onClose` / `seedDragging`)
- Produces:
  ```ts
  type ListeningPanelProps = {
    currentlyPlaying: SectionState<CurrentlyPlayingResponse>;
    recentlyPlayed: SectionState<RecentlyPlayedResponse>;
    topTracks: SectionState<TopTracksResponse>;
    topTracksRange: TopTracksRange;
    onTopTracksRangeChange: (range: TopTracksRange) => void;
    seeds: SeedTrack[];
    onClearSeeds: () => void;
    onSeedDragStart: (track: SeedTrack) => void;
    onSeedDragEnd: () => void;
    onRetryCurrentlyPlaying: () => void;
    onRetryRecentlyPlayed: () => void;
    onRetryTopTracks: () => void;
  };
  ```

- [ ] **Step 1: Create `ListeningPanel.tsx`**

Copy body from `ListeningDrawer.tsx` (search + sections + footer + `SearchResultRow`). Differences:

1. Root is `<aside className="listening-panel" aria-label="Listening">` — not `Drawer`.
2. Inner wrapper: `listening-panel-body` / `listening-panel-scroll` (mirror current `listening-drawer` / `listening-drawer-scroll` class names by renaming in JSX; keep CSS aliases in Task 2 if easier).
3. Drop the `useEffect` that clears search when `props.open` becomes false (panel stays mounted on desktop).
4. Do **not** take `open`, `onClose`, or `seedDragging`.

Skeleton:

```tsx
import { useEffect, useState } from "react";
import { searchSpotifyTracks } from "../api";
import { setSeedDragData } from "../lib/seedDrag";
import { isSeedSelected } from "../lib/seeds";
import {
  TOP_TRACKS_RANGE_LABELS,
  type TopTracksRange,
} from "../lib/topTracksRange";
import type {
  CurrentlyPlayingResponse,
  RecentlyPlayedResponse,
  SectionState,
  SeedTrack,
  TopTracksResponse,
  TrackSearchItem,
} from "../types";
import { DashboardSection } from "./DashboardSection";
import { NowPlaying } from "./NowPlaying";
import { RecentTrackList, TopTrackList } from "./TrackList";

export type ListeningPanelProps = {
  currentlyPlaying: SectionState<CurrentlyPlayingResponse>;
  recentlyPlayed: SectionState<RecentlyPlayedResponse>;
  topTracks: SectionState<TopTracksResponse>;
  topTracksRange: TopTracksRange;
  onTopTracksRangeChange: (range: TopTracksRange) => void;
  seeds: SeedTrack[];
  onClearSeeds: () => void;
  onSeedDragStart: (track: SeedTrack) => void;
  onSeedDragEnd: () => void;
  onRetryCurrentlyPlaying: () => void;
  onRetryRecentlyPlayed: () => void;
  onRetryTopTracks: () => void;
};

// SearchResultRow: copy from ListeningDrawer unchanged

export function ListeningPanel(props: ListeningPanelProps) {
  // same search state + activeQuery effect as ListeningDrawer
  // omit open-reset effect

  const selectedIds = new Set(props.seeds.map((s) => s.id));

  return (
    <aside className="listening-panel" aria-label="Listening">
      <div className="listening-panel-scroll">
        {/* search section, Now playing, Recently played, Top tracks — same as drawer */}
      </div>
      <footer className="listening-footer">{/* same footer */}</footer>
    </aside>
  );
}
```

Paste the full section markup from `ListeningDrawer` so behavior is identical.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ListeningPanel.tsx
git commit -m "feat: add ListeningPanel for built-in listening rail"
```

---

### Task 2: Layout CSS (desktop rail + mobile overlay)

**Files:**
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: class names `listening-panel`, `stage-workspace`, `app--listening-open`
- Produces: layout that places panel left of stage on desktop; off-canvas on mobile

- [ ] **Step 1: Add workspace + panel styles**

Append (or place near existing `.shell--stage` / `.listening-drawer` blocks):

```css
/* --- Listening panel (built-in nav) --- */
.stage-workspace {
  flex: 1;
  display: flex;
  align-items: stretch;
  min-height: 0;
  width: 100%;
}

.listening-panel {
  display: flex;
  flex-direction: column;
  width: 20rem;
  flex-shrink: 0;
  min-height: 0;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(12, 12, 14, 0.92);
  z-index: 3;
}

.listening-panel-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 0.85rem 0.9rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.shell--stage {
  flex: 1;
  min-width: 0;
  width: auto;
  max-width: none;
  padding-inline: 1rem;
  padding-block: 0 2rem;
}

/* Reuse listening section density: either duplicate .listening-drawer rules
   onto .listening-panel, or add selectors, e.g.: */
.listening-panel .dashboard-section { /* same as .listening-drawer .dashboard-section */ }
.listening-panel .now-playing,
.listening-panel .track-item,
.listening-panel .artist-item {
  animation: none;
}
.listening-panel .section-title { /* same as .listening-drawer .section-title */ }

/* Mobile: off-canvas */
@media (max-width: 899px) {
  .listening-panel {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: min(20rem, 88vw);
    transform: translateX(-105%);
    transition: transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
    border-right: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 8px 0 32px rgba(0, 0, 0, 0.45);
  }

  .app--listening-open .listening-panel {
    transform: translateX(0);
  }

  .listening-panel-backdrop {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 2;
    border: 0;
    padding: 0;
    background: rgba(0, 0, 0, 0.55);
    cursor: pointer;
  }

  .app--listening-open .listening-panel-backdrop {
    display: block;
  }

  .chrome-btn--listening {
    display: inline-flex;
  }
}

@media (min-width: 900px) {
  .listening-panel-backdrop {
    display: none !important;
  }

  .chrome-btn--listening {
    display: none !important;
  }
}
```

Also keep `.app--seed-dragging .match-zone` highlight (useful without drawer).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/styles.css
git commit -m "style: add listening panel rail and mobile overlay layout"
```

---

### Task 3: Wire `App` + `AppChrome`

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppChrome.tsx`

**Interfaces:**
- Consumes: `ListeningPanel`, updated chrome props
- Produces:
  - `drawer: null | "search"`
  - `listeningOpen: boolean`
  - `AppChrome`: `listeningOpen`, `onToggleListening`, `onOpenSearch` (no `onOpenListening`)

- [ ] **Step 1: Update `AppChrome`**

Replace Listening open-with:

```tsx
type AppChromeProps = {
  profile: SectionState<SpotifyProfile>;
  currentlyPlaying: SectionState<CurrentlyPlayingResponse>;
  loggingOut: boolean;
  onLogout: () => void;
  listeningOpen: boolean;
  onToggleListening: () => void;
  onOpenSearch: () => void;
};

// Listening button:
<button
  type="button"
  className={
    isPlaying
      ? "chrome-btn chrome-btn--nav chrome-btn--listening chrome-btn--live"
      : "chrome-btn chrome-btn--nav chrome-btn--listening"
  }
  aria-expanded={listeningOpen}
  aria-controls="listening-panel"
  onClick={onToggleListening}
>
  Listening
  {isPlaying ? <span className="chrome-live-dot" aria-hidden="true" /> : null}
</button>
```

Search button unchanged.

- [ ] **Step 2: Update `App.tsx` state and layout**

```tsx
const [drawer, setDrawer] = useState<null | "search">(null);
const [listeningOpen, setListeningOpen] = useState(false);
```

Logout reset: `setListeningOpen(false)` instead of only clearing listening drawer.

```tsx
const handleDropSeed = useCallback((track: SeedTrack) => {
  setSeeds((current) => {
    const { seeds: next } = addSeed(current, track);
    return next;
  });
  setSeedDragging(false);
  setListeningOpen(false); // mobile: closes panel; desktop: no visual change
}, []);

const closeDrawer = useCallback(() => setDrawer(null), []);
const closeListening = useCallback(() => setListeningOpen(false), []);
const toggleListening = useCallback(
  () => setListeningOpen((open) => !open),
  [],
);
```

Logged-in return JSX (structure):

```tsx
<div
  className={[
    "app",
    "app--stage",
    drawer ? "app--drawer-open" : "",
    listeningOpen ? "app--listening-open" : "",
    seedDragging ? "app--seed-dragging" : "",
  ]
    .filter(Boolean)
    .join(" ")}
>
  <AudioMeters active={isPlaying} />
  <AlbumConveyor imageUrls={recentCoverUrls} />
  <AppChrome
    profile={me}
    currentlyPlaying={currentlyPlaying}
    loggingOut={loggingOut}
    onLogout={() => void handleLogout()}
    listeningOpen={listeningOpen}
    onToggleListening={toggleListening}
    onOpenSearch={() => setDrawer("search")}
  />
  <button
    type="button"
    className="listening-panel-backdrop"
    aria-label="Close Listening"
    onClick={closeListening}
  />
  <div className="stage-workspace">
    <ListeningPanel
      // id for aria-controls — add id="listening-panel" on aside in ListeningPanel
      currentlyPlaying={currentlyPlaying}
      recentlyPlayed={recentlyPlayed}
      topTracks={topTracks}
      topTracksRange={topTracksRange}
      onTopTracksRangeChange={(range) => void handleTopTracksRangeChange(range)}
      seeds={seeds}
      onClearSeeds={handleClearSeeds}
      onSeedDragStart={handleSeedDragStart}
      onSeedDragEnd={handleSeedDragEnd}
      onRetryCurrentlyPlaying={() => void refreshCurrentlyPlaying()}
      onRetryRecentlyPlayed={() => void refreshRecentlyPlayed()}
      onRetryTopTracks={() => void handleTopTracksRangeChange(topTracksRange)}
    />
    <main className="shell shell--stage">
      <RecommendStage
        drawerOpen={drawer !== null || listeningOpen}
        seedDragging={seedDragging}
        seeds={seeds}
        isPlaying={isPlaying}
        onDropSeed={handleDropSeed}
        onRemoveSeed={handleRemoveSeed}
      />
    </main>
  </div>
  <SearchDrawer open={drawer === "search"} onClose={closeDrawer} />
</div>
```

Notes:

- Pass `drawerOpen={drawer !== null || listeningOpen}` so carousel keyboard nav stays disabled while Listening overlay is open on mobile.
- Add `id="listening-panel"` on the panel `aside`.
- Remove all `ListeningDrawer` imports/usage.

- [ ] **Step 3: Build check**

Run: `cd frontend && npm run build`  
Expected: success (no TS errors).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/AppChrome.tsx frontend/src/components/ListeningPanel.tsx
git commit -m "feat: wire permanent Listening panel into stage layout"
```

---

### Task 4: Copy, Drawer cleanup, delete `ListeningDrawer`

**Files:**
- Modify: `frontend/src/components/RecommendStage.tsx`
- Modify: `frontend/src/components/Drawer.tsx`
- Modify: `frontend/src/styles.css` (remove soft/pass-through Listening-only rules if unused)
- Delete: `frontend/src/components/ListeningDrawer.tsx`

**Interfaces:**
- Consumes: plain `Drawer` for Search only
- Produces: updated idle copy; no Listening drawer file

- [ ] **Step 1: Update RecommendStage lede**

In idle header:

```tsx
<p className="stage-lede">
  Drag a track from Listening onto the slot.
</p>
```

`MatchDropZone` already says “Drag one from Listening” — leave it.

- [ ] **Step 2: Simplify `Drawer.tsx`**

Remove `softBackdrop` and `passThroughBackdrop` props and related classNames / `tabIndex` special case. Search drawer uses the plain API:

```tsx
type DrawerProps = {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
};
```

- [ ] **Step 3: Delete Listening drawer + CSS leftovers**

- Delete `frontend/src/components/ListeningDrawer.tsx`.
- Remove `.drawer-root--soft-backdrop`, `.drawer-root--pass-through` (and children) if nothing else uses them.
- Optionally remove unused `.listening-drawer*` rules once panel selectors cover the same styles, or leave aliases temporarily if both class prefixes still appear — prefer one set (`.listening-panel*`) only.

- [ ] **Step 4: Build + manual smoke**

Run: `cd frontend && npm run build`  
Expected: PASS.

Manual checklist (dev servers running):

1. Desktop wide: left Listening panel visible without clicking anything; Search still opens as drawer.
2. Drag a recent/top/now-playing/search track onto the match slot → seed fills; recommend unlocks as before.
3. No Listening drawer / dimmed pass-through sheet.
4. Narrow viewport: Listening hidden; chrome Listening toggles panel; backdrop closes it; drop closes it.
5. Stage lede does not say “Open Listening”.

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src
git commit -m "refactor: remove Listening drawer; simplify Search drawer"
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Left panel desktop always on | 2, 3 |
| Mobile collapsible + toggle | 2, 3 |
| Close panel on successful drop (mobile) | 3 (`setListeningOpen(false)`) |
| Remove ListeningDrawer | 4 |
| Keep SearchDrawer | 3 |
| Same sections + search + footer | 1 |
| Remove soft/pass-through | 4 |
| Copy update | 4 |
| Drag MIME unchanged | — no change needed |
| Breakpoint ~900px | 2 |

No placeholders. Types consistent: `ListeningPanelProps` as defined in Task 1; chrome uses `listeningOpen` / `onToggleListening`.
