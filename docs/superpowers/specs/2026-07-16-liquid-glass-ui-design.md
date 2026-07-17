# Light frost liquid-glass UI restyle — Design

**Date:** 2026-07-16  
**Branch:** `feat/liquid-glass-ui`  
**Scope:** Frontend-only visual restyle of the existing recommend-first SPA + Coming soon placeholders. No API / RAG / Spotify logic changes.

## Goal

Restyle VibeCast’s current flow (landing → immersive recommend stage → Listening / Search drawers) into a **light frost liquid-glass** look: milky translucent panels, soft sky light, frosted blur — futuristic but not dark-HUD or purple-neon. Add three **Coming soon** chrome placeholders without wiring backend.

## Decisions (locked)

| Topic | Choice |
|--------|--------|
| Scope | Restyle existing flow (not a new product IA) |
| Visual | **Light frost** — bright milky glass, cool sky / aqua accents |
| Approach | CSS-first: design tokens + `.glass` utilities; small `ComingSoon` control if needed |
| Placeholders | Watchlists, Share vibe, History — disabled chrome buttons with **Soon** badge |
| Backend | Unchanged |

## Visual system

### Palette (CSS variables)

- Soft cool background gradient (sky mist → near-white), soft luminous blobs (aqua / soft blue — **no purple**).
- Glass fill: white / ice at low opacity; border: light translucent edge; top edge highlight.
- Ink: deep slate for body; muted slate-blue for secondary.
- Accent: cool aqua / sky for primary CTA (replace dark teal/amber dominance).
- Keep fonts: Fraunces (display) + Source Sans 3 (body); ensure contrast on light glass.

### Surfaces

Apply frosted glass to:

- Landing card / CTA area
- `AppChrome`
- Recommend stage (poster frame, chip row, controls)
- Drawers (sheet + backdrop tint)
- Seed chips, primary/ghost buttons

Utility classes (names flexible): `.glass`, `.glass-strong`, `.glass-btn`. Prefer `backdrop-filter: blur(...)` with solid fallbacks when unsupported.

### Motion

1. Drawer open: soft fade + slide (existing pattern, restyled).
2. Primary CTA: hover lift + soft glass highlight.
3. Subtle stage panel shimmer / light sweep (low intensity; not neon glow spam).

## Placeholders

In logged-in chrome, next to Listening / Search:

| Label | Behavior |
|--------|----------|
| Watchlists | `disabled` / `aria-disabled`, badge **Soon**, title/tooltip “Coming soon” |
| Share vibe | same |
| History | same |

No new routes, drawers, or mock data screens in this iteration. Landing stays brand + Spotify login only.

## Out of scope

- New product screens or navigation IA
- Backend endpoints for watchlists / share / history
- Dark aurora / noir themes
- Full component library rewrite (`GlassPanel` kit deferred)
- Changing recommend / seed / poll behavior

## Success criteria

1. Logged-out and logged-in first viewport read as light frost glass, not the previous dark teal/amber shell.
2. Existing flows still work: login, recommend, seeds, Listening, Search, logout.
3. Three Coming soon controls visible in chrome and clearly non-functional.
4. Usable on desktop and mobile; glass does not kill contrast or readability.
5. No backend file changes required for this feature.

## Testing

- Manual: landing, login, stage recommend, drawers, seeds, logout under new theme.
- `cd frontend && npm run build && npm run lint`
- No new backend tests.
