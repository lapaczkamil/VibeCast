# Light Frost Liquid-Glass UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the existing VibeCast SPA to a light frost liquid-glass look and add three Coming soon chrome placeholders (Watchlists, Share vibe, History) without changing backend behavior.

**Architecture:** CSS-first: replace `:root` tokens and body atmosphere; add `.glass` / `.glass-strong` / `.glass-btn` utilities; retune chrome, stage, drawers, chips, and CTAs for light frost. Add a small `ComingSoonButton` used only in `AppChrome`. No API or recommend/seed logic changes.

**Tech Stack:** React 19, TypeScript, Vite, existing `frontend/src/styles.css`, Fraunces + Source Sans 3.

## Global Constraints

- Frontend-only; do not modify `app/` or backend tests for this feature.
- Visual: **light frost** — milky glass, cool sky/aqua accents, **no purple**, not dark aurora.
- Keep fonts: Fraunces + Source Sans 3.
- Placeholders: Watchlists, Share vibe, History — disabled + **Soon** badge + “Coming soon” tooltip.
- Preserve existing flows: auth, recommend, seeds, Listening/Search drawers, now-playing poll.
- Spec: `docs/superpowers/specs/2026-07-16-liquid-glass-ui-design.md`
- Gate: `cd frontend && npm run build && npm run lint` (use Linux Node: `$HOME/.local/node/bin` on WSL).

---

## File structure

| File | Responsibility |
|------|----------------|
| `frontend/src/styles.css` | New light tokens, glass utilities, restyled surfaces, Soon badge, motion |
| `frontend/src/components/ComingSoonButton.tsx` | Disabled chrome control + Soon badge |
| `frontend/src/components/AppChrome.tsx` | Insert three Coming soon buttons |
| Optionally touch classNames in `App.tsx` / `RecommendStage.tsx` / `Drawer.tsx` only if a `glass` class must be added on a root element |

---

### Task 1: Light frost tokens + glass restyle

**Files:**
- Modify: `frontend/src/styles.css` (`:root`, `body`, chrome, stage, drawer, CTA, chips, landing)

**Interfaces:**
- CSS variables (exact names to use):
  ```css
  --bg-deep: #e8f1f8;
  --bg-mid: #f7fbfe;
  --ink: #1a2330;
  --ink-muted: #5a6b7d;
  --accent: #1aa7b8;
  --accent-glow: rgba(26, 167, 184, 0.28);
  --amber: #c4893a; /* keep sparingly for warnings only */
  --glass-fill: rgba(255, 255, 255, 0.55);
  --glass-fill-strong: rgba(255, 255, 255, 0.72);
  --glass-border: rgba(255, 255, 255, 0.65);
  --glass-edge: rgba(26, 50, 80, 0.08);
  --border: rgba(26, 50, 80, 0.1);
  ```
- Utilities:
  ```css
  .glass { background: var(--glass-fill); backdrop-filter: blur(18px) saturate(1.2); -webkit-backdrop-filter: blur(18px) saturate(1.2); border: 1px solid var(--glass-border); box-shadow: 0 8px 32px rgba(26, 50, 80, 0.08), inset 0 1px 0 rgba(255,255,255,0.7); }
  .glass-strong { /* stronger fill */ }
  .glass-btn { /* frosted button base */ }
  ```

- [ ] **Step 1: Replace `:root` + body atmosphere**

Update `:root` to the light tokens above. Replace dark body background with cool mist gradient + soft aqua/sky blobs (no purple). Reduce or remove the heavy dark noise overlay; optional very light grain at ≤0.03 opacity.

- [ ] **Step 2: Add glass utilities**

Append `.glass`, `.glass-strong`, `.glass-btn` near the top after `:root`. Provide `@supports not ((backdrop-filter: blur(1px)))` fallback with higher opacity fill.

- [ ] **Step 3: Restyle key surfaces**

Retune for light frost (ink contrast, glass fills, soft borders):

- `.chrome`, `.chrome-btn` → glass-btn look
- `.shell--landing`, landing CTA
- `.cta--primary` / `.cta--ghost` — aqua gradient / glass ghost (avoid dark deep bg text colors)
- `.drawer-sheet`, `.drawer-backdrop` (light frosted sheet; backdrop rgba slate soft)
- `.stage`, `.stage-poster`, `.stage-nav`, `.stage-dot`, seed chips (`.seed-chip` if present)
- `.avatar`, profile cluster, status/error messages (amber only for warnings)

Ensure brand titles remain readable dark slate, not white-on-white.

- [ ] **Step 4: Build check**

```bash
export PATH="$HOME/.local/node/bin:$PATH"
cd frontend && npm run build
```

Expected: success.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/styles.css
git commit -m "style(ui): restyle app to light frost liquid glass"
```

---

### Task 2: Coming soon placeholders + motion polish

**Files:**
- Create: `frontend/src/components/ComingSoonButton.tsx`
- Modify: `frontend/src/components/AppChrome.tsx`
- Modify: `frontend/src/styles.css` (Soon badge + motion)

**Interfaces:**
```tsx
type ComingSoonButtonProps = {
  label: string;
};

export function ComingSoonButton({ label }: ComingSoonButtonProps) {
  return (
    <button
      type="button"
      className="chrome-btn chrome-btn--soon"
      disabled
      aria-disabled="true"
      title="Coming soon"
    >
      <span>{label}</span>
      <span className="soon-badge" aria-hidden="true">Soon</span>
    </button>
  );
}
```

In `AppChrome`, after Search button, render:

```tsx
<ComingSoonButton label="Watchlists" />
<ComingSoonButton label="Share vibe" />
<ComingSoonButton label="History" />
```

- [ ] **Step 1: Add ComingSoonButton + wire AppChrome**

Create component; import and place in `chrome-actions` between Search and profile cluster.

- [ ] **Step 2: Soon badge + disabled glass styles**

```css
.chrome-btn--soon {
  opacity: 0.72;
  cursor: not-allowed;
  gap: 0.4rem;
  display: inline-flex;
  align-items: center;
}
.soon-badge {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 0.15rem 0.35rem;
  border-radius: 0.35rem;
  background: rgba(26, 167, 184, 0.15);
  color: var(--accent);
  border: 1px solid rgba(26, 167, 184, 0.25);
}
```

On small screens, allow chrome-actions wrap (already flex-wrap).

- [ ] **Step 3: Motion polish**

Ensure/adjust:

1. Drawer slide/fade still present.
2. `.cta--primary:hover` lift + soft aqua glow (`--accent-glow`).
3. Subtle shimmer on `.stage-inner` or `.glass` stage panel — e.g. `::after` linear-gradient sweep, 6–8s loop, opacity ≤0.35, `pointer-events: none`.

- [ ] **Step 4: Verify**

```bash
export PATH="$HOME/.local/node/bin:$PATH"
cd frontend && npm run build && npm run lint
```

Manual glance with `npm run dev`: landing light frost; logged-in chrome shows three Soon buttons disabled; drawers/stage readable.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ComingSoonButton.tsx frontend/src/components/AppChrome.tsx frontend/src/styles.css
git commit -m "feat(ui): add Coming soon chrome placeholders and glass motion"
```

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| Light frost tokens / no purple | 1 |
| Glass surfaces (landing, chrome, stage, drawers, chips, CTA) | 1 |
| Coming soon: Watchlists, Share vibe, History | 2 |
| Motion (drawer, CTA hover, shimmer) | 2 |
| No backend changes | Global |
| Build/lint gate | 1–2 |

No placeholders left in the plan. Exact button labels locked.
