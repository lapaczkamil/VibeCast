# Immersive Recommend-First UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the React SPA so the logged-in experience is an immersive one-movie-at-a-time recommendation stage, with Spotify listening data and TMDB search available only via right-side drawers.

**Architecture:** Keep existing API clients and Spotify/TMDB list components. Add a shared `Drawer`, slim `AppChrome`, and `RecommendStage` (carousel). `App` owns auth, Spotify section state (for Listening), and exclusive drawer open state (`null | "listening" | "search"`). Landing drops `MoviesSearch`. No backend changes.

**Tech Stack:** React 19, TypeScript, Vite, existing CSS in `frontend/src/styles.css` (Fraunces + Source Sans 3, teal/amber dark palette).

## Global Constraints

- Frontend-only; do not change FastAPI / RAG / Spotify / TMDB routes.
- Drawer pattern: same right sheet on desktop and mobile (not a persistent sidebar, not a bottom tab bar).
- Carousel: one movie at a time; prev/next, swipe, and ←/→ when no drawer is open.
- Landing: brand + Spotify login only (no TMDB while logged out).
- Keep existing CSS variables and fonts; refresh composition/density, not rebrand.
- Do not auto-run recommend on login; button-driven only.
- Automated gate: `cd frontend && npm run build` (and `npm run lint` if clean). No frontend unit-test runner exists — do not add Vitest unless a pure helper is introduced; prefer manual checklist from the spec.
- Spec: `docs/superpowers/specs/2026-07-16-immersive-recommend-ui-design.md`

---

## File structure

| File | Responsibility |
|------|----------------|
| `frontend/src/lib/carouselIndex.ts` | Pure `nextIndex` / `prevIndex` wrapping |
| `frontend/src/components/Drawer.tsx` | Backdrop + right sheet; Esc / backdrop / close |
| `frontend/src/components/AppChrome.tsx` | Brand, Listening, Search, avatar, logout (replaces `ProfileHeader` usage) |
| `frontend/src/components/RecommendStage.tsx` | Idle / loading / success carousel / empty / error (replaces `RecommendSection`) |
| `frontend/src/components/ListeningDrawer.tsx` | Drawer wrapping existing Spotify sections |
| `frontend/src/components/SearchDrawer.tsx` | Drawer wrapping `MoviesSearch` |
| `frontend/src/App.tsx` | Auth + drawer state + stage layout; no main-column Spotify/Movies stacks |
| `frontend/src/styles.css` | Immersive stage, chrome, drawer, compact listening lists |
| `frontend/src/components/ProfileHeader.tsx` | Delete after `AppChrome` lands (or leave unused — prefer delete) |
| `frontend/src/components/RecommendSection.tsx` | Delete after `RecommendStage` lands |

Reuse unchanged: `DashboardSection`, `NowPlaying`, track/artist lists, `MoviesSearch`, `api.ts`, `types.ts`.

---

### Task 1: Carousel index helper + Drawer

**Files:**
- Create: `frontend/src/lib/carouselIndex.ts`
- Create: `frontend/src/components/Drawer.tsx`
- Modify: `frontend/src/styles.css` (append drawer styles)

**Interfaces:**
- Consumes: React only
- Produces:
  - `nextIndex(current: number, length: number): number`
  - `prevIndex(current: number, length: number): number`
  - `Drawer` props:
    ```ts
    type DrawerProps = {
      title: string;
      open: boolean;
      onClose: () => void;
      children: React.ReactNode;
    };
    ```

- [ ] **Step 1: Add carousel helpers**

Create `frontend/src/lib/carouselIndex.ts`:

```ts
/** Wrap-around next index; returns 0 if length <= 0. */
export function nextIndex(current: number, length: number): number {
  if (length <= 0) return 0;
  return (current + 1) % length;
}

/** Wrap-around previous index; returns 0 if length <= 0. */
export function prevIndex(current: number, length: number): number {
  if (length <= 0) return 0;
  return (current - 1 + length) % length;
}
```

- [ ] **Step 2: Add Drawer component**

Create `frontend/src/components/Drawer.tsx`:

```tsx
import { useEffect, type ReactNode } from "react";

type DrawerProps = {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
};

export function Drawer({ title, open, onClose, children }: DrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="drawer-root" role="presentation">
      <button
        type="button"
        className="drawer-backdrop"
        aria-label="Close panel"
        onClick={onClose}
      />
      <aside
        className="drawer-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="drawer-header">
          <h2 className="drawer-title">{title}</h2>
          <button
            type="button"
            className="drawer-close"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}
```

- [ ] **Step 3: Append drawer CSS**

Append to `frontend/src/styles.css`:

```css
.drawer-root {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  justify-content: flex-end;
}

.drawer-backdrop {
  position: absolute;
  inset: 0;
  border: none;
  padding: 0;
  background: rgba(0, 0, 0, 0.5);
  cursor: pointer;
  animation: drawer-fade 200ms ease-out both;
}

.drawer-sheet {
  position: relative;
  z-index: 1;
  width: min(22rem, 92vw);
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-mid);
  border-left: 1px solid var(--border);
  box-shadow: -16px 0 48px rgba(0, 0, 0, 0.45);
  animation: drawer-slide 220ms ease-out both;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 1rem 1.1rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.drawer-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 600;
}

.drawer-close {
  border: none;
  background: transparent;
  color: var(--ink-muted);
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  padding: 0.25rem 0.4rem;
}

.drawer-close:hover {
  color: var(--ink);
}

.drawer-body {
  overflow: auto;
  padding: 1rem 1.1rem 2rem;
  flex: 1;
}

@keyframes drawer-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes drawer-slide {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && npm run build`  
Expected: success (TypeScript + Vite).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/carouselIndex.ts frontend/src/components/Drawer.tsx frontend/src/styles.css
git commit -m "feat(ui): add drawer shell and carousel index helpers"
```

---

### Task 2: AppChrome

**Files:**
- Create: `frontend/src/components/AppChrome.tsx`
- Modify: `frontend/src/styles.css` (chrome button styles)
- Delete later (Task 4): `frontend/src/components/ProfileHeader.tsx`

**Interfaces:**
- Consumes: `SectionState<SpotifyProfile>` from `../types`
- Produces:
  ```ts
  type AppChromeProps = {
    profile: SectionState<SpotifyProfile>;
    loggingOut: boolean;
    onLogout: () => void;
    onOpenListening: () => void;
    onOpenSearch: () => void;
  };
  ```

- [ ] **Step 1: Create AppChrome**

Create `frontend/src/components/AppChrome.tsx` (reuse avatar/initials logic from `ProfileHeader.tsx`):

```tsx
import type { SectionState, SpotifyProfile } from "../types";

function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

type AppChromeProps = {
  profile: SectionState<SpotifyProfile>;
  loggingOut: boolean;
  onLogout: () => void;
  onOpenListening: () => void;
  onOpenSearch: () => void;
};

export function AppChrome({
  profile,
  loggingOut,
  onLogout,
  onOpenListening,
  onOpenSearch,
}: AppChromeProps) {
  const displayName =
    profile.status === "ok" ? profile.data!.display_name : "…";
  const imageUrl =
    profile.status === "ok" ? profile.data!.image_url : null;

  return (
    <header className="chrome">
      <h1 className="brand brand--chrome">VibeCast</h1>
      <div className="chrome-actions">
        <button
          type="button"
          className="chrome-btn"
          onClick={onOpenListening}
        >
          Listening
        </button>
        <button type="button" className="chrome-btn" onClick={onOpenSearch}>
          Search
        </button>
        <div className="profile-cluster profile-cluster--chrome">
          <div className="avatar" aria-hidden={profile.status !== "ok"}>
            {imageUrl ? (
              <img src={imageUrl} alt="" className="avatar-img" />
            ) : (
              <span className="avatar-initials">
                {profile.status === "ok"
                  ? initialsFromName(profile.data!.display_name)
                  : "…"}
              </span>
            )}
          </div>
          <span className="profile-name">{displayName}</span>
          <button
            type="button"
            className="cta cta--ghost cta--logout"
            onClick={onLogout}
            disabled={loggingOut}
          >
            {loggingOut ? "Logging out…" : "Log out"}
          </button>
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Add chrome CSS**

Append to `frontend/src/styles.css`:

```css
.chrome {
  width: min(56rem, 100% - 2rem);
  margin-inline: auto;
  padding-block: 1rem 0.25rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem 1rem;
}

.brand--chrome {
  font-size: clamp(1.5rem, 4vw, 2rem);
  line-height: 1;
}

.chrome-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.65rem;
}

.chrome-btn {
  font-family: var(--font-body);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--ink-muted);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 0.45rem;
  padding: 0.4rem 0.75rem;
  cursor: pointer;
}

.chrome-btn:hover {
  color: var(--ink);
  background: rgba(255, 255, 255, 0.04);
}

.profile-cluster--chrome {
  margin-left: 0.25rem;
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`  
Expected: success.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AppChrome.tsx frontend/src/styles.css
git commit -m "feat(ui): add slim AppChrome with Listening and Search"
```

---

### Task 3: RecommendStage (immersive carousel)

**Files:**
- Create: `frontend/src/components/RecommendStage.tsx`
- Modify: `frontend/src/styles.css` (stage / carousel styles)
- Later delete: `frontend/src/components/RecommendSection.tsx`

**Interfaces:**
- Consumes: `fetchRagStatus`, `requestRecommendations` from `../api`; `nextIndex` / `prevIndex` from `../lib/carouselIndex`; types `RagStatus`, `RecommendMovieItem`, `RecommendResponse`
- Produces: `<RecommendStage drawerOpen: boolean />` — when `drawerOpen` is true, ignore keyboard arrows

- [ ] **Step 1: Implement RecommendStage**

Create `frontend/src/components/RecommendStage.tsx` by evolving `RecommendSection`:

- Keep RAG status fetch, `canRecommend`, warning copy, `runRecommend` / phases.
- On success: `activeIndex` state (reset to `0` whenever new results arrive).
- Render one `items[activeIndex]` with large poster, title, year, reason.
- Show `mood_summary` as muted line if present.
- Prev/next buttons call `prevIndex` / `nextIndex`.
- Dot row for position.
- “Match again” calls `runRecommend` (same as primary when already in `ok`).
- Idle: poster placeholder + “Recommend movies”.
- Loading: skeleton poster + “Matching movies to your vibe…”.
- Touch: `onTouchStart` / `onTouchEnd` — if deltaX > 50px, prev/next.
- Keyboard: `useEffect` on `window` for `ArrowLeft` / `ArrowRight` when `!drawerOpen` and phase is `ok`.

Key structure (implement fully in the file; do not leave stubs):

```tsx
type RecommendStageProps = {
  drawerOpen: boolean;
};

export function RecommendStage({ drawerOpen }: RecommendStageProps) {
  // ... status + phase state from RecommendSection ...
  const [activeIndex, setActiveIndex] = useState(0);

  // after successful requestRecommendations:
  // setResults(data); setActiveIndex(0); setPhase(...)

  // keyboard + swipe handlers using nextIndex/prevIndex
  // ...
}
```

Poster sizing: CSS class `stage-poster` (~160–200px wide on desktop, slightly smaller on mobile). Do not put badges/chips on the poster.

- [ ] **Step 2: Add stage CSS**

Append immersive stage styles (names can vary slightly but keep these roles):

```css
.stage {
  width: min(40rem, 100% - 2rem);
  margin-inline: auto;
  min-height: calc(100vh - 5.5rem);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding-block: 1rem 2.5rem;
  position: relative;
}

.stage-wash {
  pointer-events: none;
  position: absolute;
  inset: -10% -20% auto;
  height: 70%;
  background: radial-gradient(
    ellipse 70% 60% at 50% 40%,
    var(--accent-glow),
    transparent 70%
  );
  opacity: 0.55;
  z-index: 0;
}

.stage-inner {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
}

.stage-eyebrow {
  margin: 0;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.stage-carousel {
  display: flex;
  align-items: center;
  gap: 1rem;
  width: 100%;
  justify-content: center;
}

.stage-nav {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: rgba(0, 0, 0, 0.25);
  color: var(--ink);
  cursor: pointer;
  font-size: 1.25rem;
  line-height: 1;
}

.stage-poster {
  width: clamp(9rem, 32vw, 12.5rem);
  aspect-ratio: 2 / 3;
  object-fit: cover;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.5);
  background: rgba(255, 255, 255, 0.04);
}

.stage-poster--placeholder,
.stage-poster--skeleton {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-muted);
}

.stage-poster--skeleton {
  animation: stage-pulse 1.2s ease-in-out infinite;
}

@keyframes stage-pulse {
  0%, 100% { opacity: 0.45; }
  50% { opacity: 0.85; }
}

.stage-title {
  margin: 0.5rem 0 0;
  font-family: var(--font-display);
  font-size: clamp(1.35rem, 4vw, 1.75rem);
  font-weight: 600;
}

.stage-year,
.stage-mood,
.stage-reason {
  margin: 0;
  color: var(--ink-muted);
}

.stage-reason {
  max-width: 28rem;
  color: var(--ink);
  line-height: 1.45;
  font-size: 0.98rem;
}

.stage-dots {
  display: flex;
  gap: 0.35rem;
  margin: 0.25rem 0;
}

.stage-dot {
  width: 0.4rem;
  height: 0.4rem;
  border-radius: 50%;
  background: rgba(232, 237, 242, 0.25);
  border: none;
  padding: 0;
  cursor: pointer;
}

.stage-dot--active {
  background: var(--accent);
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`  
Expected: success (component unused until Task 4 is fine).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/RecommendStage.tsx frontend/src/styles.css
git commit -m "feat(ui): add immersive RecommendStage carousel"
```

---

### Task 4: Wire App — drawers, landing, remove dashboard stack

**Files:**
- Create: `frontend/src/components/ListeningDrawer.tsx`
- Create: `frontend/src/components/SearchDrawer.tsx`
- Modify: `frontend/src/App.tsx` (full logged-in + landing composition)
- Delete: `frontend/src/components/ProfileHeader.tsx`
- Delete: `frontend/src/components/RecommendSection.tsx`
- Modify: `frontend/src/styles.css` (compact `.drawer-body .dashboard-section` spacing if needed)

**Interfaces:**
- Consumes: `AppChrome`, `RecommendStage`, `Drawer` (via Listening/Search wrappers), existing section components + `loadDashboard` fetches
- Produces: `drawer: null | "listening" | "search"` in `App`; opening one closes the other

- [ ] **Step 1: ListeningDrawer**

```tsx
import { Drawer } from "./Drawer";
import { DashboardSection } from "./DashboardSection";
import { NowPlaying } from "./NowPlaying";
import { ArtistList } from "./ArtistList";
import { RecentTrackList, TopTrackList } from "./TrackList";
import type {
  CurrentlyPlayingResponse,
  RecentlyPlayedResponse,
  SectionState,
  TopArtistsResponse,
  TopTracksResponse,
} from "../types";

type ListeningDrawerProps = {
  open: boolean;
  onClose: () => void;
  currentlyPlaying: SectionState<CurrentlyPlayingResponse>;
  recentlyPlayed: SectionState<RecentlyPlayedResponse>;
  topTracks: SectionState<TopTracksResponse>;
  topArtists: SectionState<TopArtistsResponse>;
  onRetryCurrentlyPlaying: () => void;
  onRetryRecentlyPlayed: () => void;
  onRetryTopTracks: () => void;
  onRetryTopArtists: () => void;
};

export function ListeningDrawer(props: ListeningDrawerProps) {
  return (
    <Drawer title="Listening" open={props.open} onClose={props.onClose}>
      <div className="listening-drawer">
        <DashboardSection
          title="Now playing"
          state={props.currentlyPlaying}
          onRetry={props.onRetryCurrentlyPlaying}
        >
          {(data) => <NowPlaying data={data} />}
        </DashboardSection>
        {/* Recently played, Top tracks, Top artists — same pattern */}
      </div>
    </Drawer>
  );
}
```

Implement all four sections (copy retry handlers from current `App.tsx`).

- [ ] **Step 2: SearchDrawer**

```tsx
import { Drawer } from "./Drawer";
import { MoviesSearch } from "./MoviesSearch";

type SearchDrawerProps = {
  open: boolean;
  onClose: () => void;
};

export function SearchDrawer({ open, onClose }: SearchDrawerProps) {
  return (
    <Drawer title="Search movies" open={open} onClose={onClose}>
      <MoviesSearch />
    </Drawer>
  );
}
```

- [ ] **Step 3: Rewrite logged-in + landing branches in App.tsx**

1. Add `const [drawer, setDrawer] = useState<null | "listening" | "search">(null);`
2. Logged-out: remove `<MoviesSearch showTitle />` — only brand, subtitle, auth error, Spotify CTA.
3. Logged-in main:

```tsx
return (
  <div className="app app--stage">
    <AppChrome
      profile={me}
      loggingOut={loggingOut}
      onLogout={() => void handleLogout()}
      onOpenListening={() => setDrawer("listening")}
      onOpenSearch={() => setDrawer("search")}
    />
    <main className="shell shell--stage">
      <RecommendStage drawerOpen={drawer !== null} />
    </main>
    <ListeningDrawer
      open={drawer === "listening"}
      onClose={() => setDrawer(null)}
      currentlyPlaying={currentlyPlaying}
      recentlyPlayed={recentlyPlayed}
      topTracks={topTracks}
      topArtists={topArtists}
      onRetryCurrentlyPlaying={/* existing retry */}
      onRetryRecentlyPlayed={/* existing retry */}
      onRetryTopTracks={/* existing retry */}
      onRetryTopArtists={/* existing retry */}
    />
    <SearchDrawer
      open={drawer === "search"}
      onClose={() => setDrawer(null)}
    />
  </div>
);
```

4. Keep `loadDashboard` after auth (Listening still needs data).
5. On logout, also `setDrawer(null)`.
6. Remove imports of `ProfileHeader`, `RecommendSection`, and main-column `DashboardSection` / Movies section.

- [ ] **Step 4: Compact drawer list CSS**

```css
.listening-drawer .dashboard-section {
  margin-bottom: 1.25rem;
}

.listening-drawer .section-title {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-muted);
}
```

- [ ] **Step 5: Delete obsolete components**

Delete `ProfileHeader.tsx` and `RecommendSection.tsx` if nothing imports them.

- [ ] **Step 6: Verify build + lint**

Run:

```bash
cd frontend && npm run build && npm run lint
```

Expected: build success; lint clean or only pre-existing issues unrelated to this change.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/ListeningDrawer.tsx frontend/src/components/SearchDrawer.tsx frontend/src/styles.css
git add -u frontend/src/components/ProfileHeader.tsx frontend/src/components/RecommendSection.tsx
git commit -m "feat(ui): recommend-first stage with Listening and Search drawers"
```

---

### Task 5: Polish + manual verification

**Files:**
- Modify: `frontend/src/styles.css` only if polish needed (stage motion, landing focus)
- Touch components only for bugs found in manual pass

- [ ] **Step 1: Motion polish (min 2–3 intentional motions)**

Ensure present:
1. Drawer slide/fade (Task 1)
2. Stage poster / title fade-in on result change (`animation: brand-fade-in` or similar on `.stage-title` / poster)
3. Primary CTA hover lift (existing `.cta--primary:hover`)

Optional: fade wash slightly when results load.

- [ ] **Step 2: Manual checklist**

With `uvicorn` + `npm run dev`:

1. Logged-out landing: brand + login only (no Movies search).
2. Login → idle stage + Recommend CTA.
3. Recommend (Ollama + index ready) → carousel; ‹ ›, dots, swipe, ←/→.
4. Match again → new results, index resets to first.
5. Listening opens sheet with Spotify sections; Esc / backdrop / × closes.
6. Search opens TMDB search; opening Search while Listening is open replaces it.
7. Logout returns to landing; drawer closed.
8. Mobile width (~375px): stage usable, drawer ~92vw.

- [ ] **Step 3: Final build**

Run: `cd frontend && npm run build`  
Expected: success.

- [ ] **Step 4: Commit polish if any file changes**

```bash
git add frontend/src/styles.css frontend/src/
git commit -m "style(ui): polish immersive stage motion and density"
```

(Skip empty commit if nothing changed.)

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Recommend-first main screen / immersive stage | 3, 4 |
| Listening + Search drawers (same desktop/mobile) | 1, 4 |
| One movie carousel + arrows / swipe / keyboard | 1, 3 |
| Landing without TMDB | 4 |
| Keep palette/fonts | Global + CSS tasks |
| No API changes / no auto-recommend | Global |
| Success criteria + manual testing | 5 |

No placeholders left. Types/names consistent: `drawer: null | "listening" | "search"`, `RecommendStage({ drawerOpen })`, `nextIndex` / `prevIndex`.
