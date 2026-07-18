from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import HTTPException

from app.config import settings
from app.movies.client import _map_poster_url, _map_rating, fetch_movie
from app.rag.ollama_client import chat_json, embed_texts
from app.rag.schemas import (
    RecommendMovieItem,
    RecommendRequest,
    RecommendResponse,
    RecommendTrackSeed,
)
from app.rag.store import query_movies
from app.reccobeats.client import fetch_audio_features
from app.reccobeats.mood import format_audio_profile
from app.reccobeats.rerank import rerank_candidates
from app.spotify.client import (
    fetch_currently_playing,
    fetch_recently_played,
    fetch_top_artists,
    fetch_top_tracks,
    map_currently_playing,
    map_recently_played,
    map_top_artists,
    map_top_tracks,
)
from app.spotify.routes import _authed_spotify

RAG_TOP_K = 8
RAG_FETCH_K = 16
RECENT_LIMIT = 10
TOP_TRACKS_LIMIT = 5
TOP_ARTISTS_LIMIT = 5
MAX_SEEDS = 1


class RecommendationParseError(Exception):
    pass


def build_mood_query(
    now_playing_line: str | None = None,
    recent_lines: list[str] | None = None,
    top_track_lines: list[str] | None = None,
    top_artist_lines: list[str] | None = None,
) -> str:
    parts: list[str] = []
    if now_playing_line:
        parts.append(now_playing_line)
    if recent_lines:
        parts.append("Recently played: " + ", ".join(recent_lines))
    if top_track_lines:
        parts.append("Top tracks: " + ", ".join(top_track_lines))
    if top_artist_lines:
        parts.append("Top artists: " + ", ".join(top_artist_lines))
    return "\n".join(parts)


def parse_recommendation_json(raw: str) -> list[dict[str, Any]]:
    data = json.loads(raw)
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    return items


def _track_line(name: str, artists: list[str]) -> str:
    return f"{name} by {', '.join(artists)}"


def _artist_line(name: str, genres: list[str]) -> str:
    if genres:
        return f"{name} ({', '.join(genres)})"
    return name


def _build_recommendation_prompt(
    mood_query: str,
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> str:
    candidates: list[str] = []
    for document, metadata in zip(documents, metadatas, strict=True):
        tmdb_id = metadata.get("tmdb_id")
        title = metadata.get("title", "Unknown")
        candidates.append(f"- tmdb_id={tmdb_id}, title={title!r}\n{document}")

    candidate_block = "\n\n".join(candidates)
    return f"""You recommend movies based on a listener's music mood.

Music context:
{mood_query}

Candidate movies (choose ONLY from this list):
{candidate_block}

Pick 3 to 5 movies from the candidates above that best match the music mood.
Return JSON only with this shape:
{{"mood_summary": "short string", "items": [{{"tmdb_id": number, "title": "string", "reason": "string"}}]}}
Each item must use a tmdb_id from the candidate list. Do not invent movies."""


async def _now_playing_line_only() -> str | None:
    cp_response = await _authed_spotify(fetch_currently_playing)
    if cp_response.status_code == 200 and cp_response.content:
        cp = map_currently_playing(cp_response.json())
        if cp.track is not None:
            return "Now: " + _track_line(cp.track.name, cp.track.artists)
    return None


def _normalize_seeds(tracks: list[RecommendTrackSeed]) -> list[RecommendTrackSeed]:
    seen: set[str] = set()
    out: list[RecommendTrackSeed] = []
    for t in tracks:
        if t.id in seen:
            continue
        seen.add(t.id)
        out.append(t)
    return out


def _build_mood_from_seeds(seeds: list[RecommendTrackSeed]) -> str:
    lines = [_track_line(t.name, t.artists) for t in seeds]
    return "Selected tracks: " + ", ".join(lines)


async def _gather_spotify_lines() -> tuple[str | None, list[str], list[str], list[str]]:
    cp_response = await _authed_spotify(fetch_currently_playing)
    now_playing_line: str | None = None
    if cp_response.status_code == 200 and cp_response.content:
        cp = map_currently_playing(cp_response.json())
        if cp.track is not None:
            now_playing_line = "Now: " + _track_line(cp.track.name, cp.track.artists)

    recent_response = await _authed_spotify(
        lambda token: fetch_recently_played(token, RECENT_LIMIT)
    )
    if recent_response.status_code != 200:
        raise HTTPException(status_code=502, detail="Spotify API request failed")
    recent_lines = [
        _track_line(item.name, item.artists)
        for item in map_recently_played(recent_response.json())
    ]

    top_tracks_response = await _authed_spotify(
        lambda token: fetch_top_tracks(token, TOP_TRACKS_LIMIT, "medium_term")
    )
    if top_tracks_response.status_code != 200:
        raise HTTPException(status_code=502, detail="Spotify API request failed")
    top_track_lines = [
        _track_line(item.name, item.artists)
        for item in map_top_tracks(top_tracks_response.json())
    ]

    top_artists_response = await _authed_spotify(
        lambda token: fetch_top_artists(token, TOP_ARTISTS_LIMIT, "medium_term")
    )
    if top_artists_response.status_code != 200:
        raise HTTPException(status_code=502, detail="Spotify API request failed")
    top_artist_lines = [
        _artist_line(item.name, item.genres)
        for item in map_top_artists(top_artists_response.json())
    ]

    return now_playing_line, recent_lines, top_track_lines, top_artist_lines


def overview_from_document(document: str) -> str:
    """Extract TMDB overview text from a Chroma movie document."""
    lines = document.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("Overview:"):
            first = line.removeprefix("Overview:").strip()
            rest = "\n".join(lines[index + 1 :]).strip()
            parts = [part for part in (first, rest) if part]
            return "\n".join(parts).strip()
    return ""


def _map_validated_items(
    llm_items: list[dict[str, Any]],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> list[RecommendMovieItem]:
    candidates_by_id: dict[int, dict[str, Any]] = {}
    overview_by_id: dict[int, str] = {}
    for document, metadata in zip(documents, metadatas, strict=True):
        tmdb_id = metadata.get("tmdb_id")
        if tmdb_id is None:
            continue
        key = int(tmdb_id)
        candidates_by_id[key] = metadata
        overview_by_id[key] = overview_from_document(document)

    validated: list[RecommendMovieItem] = []
    for item in llm_items:
        tmdb_id = item.get("tmdb_id")
        if tmdb_id is None:
            continue
        meta = candidates_by_id.get(int(tmdb_id))
        if meta is None:
            continue
        year = meta.get("year") or None
        if year == "":
            year = None
        validated.append(
            RecommendMovieItem(
                tmdb_id=int(tmdb_id),
                title=str(item.get("title") or meta.get("title") or "Unknown"),
                year=year,
                poster_url=_map_poster_url(meta.get("poster_path"), size="w780"),
                rating=_map_rating(meta.get("rating")),
                reason=str(item.get("reason") or ""),
                overview=overview_by_id.get(int(tmdb_id), ""),
            )
        )
    return validated


async def _enrich_missing_ratings(
    items: list[RecommendMovieItem],
) -> list[RecommendMovieItem]:
    api_key = settings.tmdb_api_key
    missing = [item for item in items if item.rating is None]
    if not api_key or not missing:
        return items

    async def _rating_for(item: RecommendMovieItem) -> float | None:
        try:
            response = await fetch_movie(api_key, item.tmdb_id)
            if response.status_code != 200:
                return None
            return _map_rating(response.json().get("vote_average"))
        except Exception:
            return None

    ratings = await asyncio.gather(*[_rating_for(item) for item in missing])
    by_id = {
        item.tmdb_id: rating
        for item, rating in zip(missing, ratings, strict=True)
        if rating is not None
    }
    if not by_id:
        return items

    return [
        item.model_copy(update={"rating": by_id[item.tmdb_id]})
        if item.tmdb_id in by_id
        else item
        for item in items
    ]


async def recommend_for_user(
    request: RecommendRequest | None = None,
) -> RecommendResponse:
    request = request or RecommendRequest()
    if len(request.tracks) > MAX_SEEDS:
        raise HTTPException(status_code=422, detail="At most 1 track allowed")

    seeds = _normalize_seeds(request.tracks)
    if seeds:
        mood_query = _build_mood_from_seeds(seeds)
    else:
        now_playing_line = await _now_playing_line_only()
        if not now_playing_line:
            raise HTTPException(
                status_code=400,
                detail="Select at least one track or start playing music",
            )
        mood_query = now_playing_line

    features = None
    seed_id: str | None = seeds[0].id if seeds else None
    if seed_id:
        features = await fetch_audio_features(seed_id)
    if features is not None:
        profile = format_audio_profile(features)
        if profile:
            mood_query = f"{mood_query}\nAudio profile: {profile}"

    embedding = embed_texts([mood_query])[0]
    fetch_k = RAG_FETCH_K if features is not None else RAG_TOP_K
    documents, metadatas = query_movies(embedding, fetch_k)
    if features is not None and documents:
        documents, metadatas = rerank_candidates(
            documents, metadatas, features, keep=RAG_TOP_K
        )
    else:
        documents, metadatas = documents[:RAG_TOP_K], metadatas[:RAG_TOP_K]

    prompt = _build_recommendation_prompt(mood_query, documents, metadatas)
    raw = chat_json(prompt)

    try:
        parsed = json.loads(raw)
        mood_summary = str(parsed.get("mood_summary") or "")
        llm_items = parse_recommendation_json(raw)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise RecommendationParseError() from exc

    items = _map_validated_items(llm_items, documents, metadatas)
    items = await _enrich_missing_ratings(items)
    return RecommendResponse(
        mood_summary=mood_summary,
        items=items,
    )
