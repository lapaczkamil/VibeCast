# Movie overview lightbox — Design

**Date:** 2026-07-18  
**Status:** Approved  

## Goal

Clicking the active recommendation poster opens an aesthetic lightbox with the TMDB overview (from Chroma document text).

## Decisions

| Topic | Choice |
|-------|--------|
| UI | Full-screen dimmed lightbox (Esc / backdrop / ×) |
| Data | `overview` on `RecommendMovieItem`, parsed from Chroma doc `Overview:` line |
| Scope | Recommend stage only (not Search drawer) |
| Empty | Show “No overview.” |

## Backend

- Add `overview: str = ""` to `RecommendMovieItem` / FE `RecommendMovieItem` type
- When mapping validated items, parse overview from the matching candidate document
- No re-ingest, no TMDB fetch on click

## Frontend

- Current poster is clickable (`button` or role=button)
- Modal: poster + title / year / rating + scrollable overview
- Cinema aesthetic; focus trap; `aria-modal`
- Close: ×, Escape, backdrop click

## Non-goals

- Search drawer lightbox
- Live TMDB refetch
- Storing overview in Chroma metadata
