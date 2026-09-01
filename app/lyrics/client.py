"""Lyrics lookup via LRCLIB, which needs no API key or authentication."""

import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = "VibeCast (https://github.com/lapaczkamil/VibeCast)"
_CACHE_TTL_SECONDS = 86400.0

_cache: dict[tuple[str, str], tuple[float, str | None]] = {}


def clear_lyrics_cache() -> None:
    _cache.clear()


def _unique_lines(lyrics: str) -> list[str]:
    """Drop blanks and repeats: choruses carry no extra signal."""
    seen: set[str] = set()
    lines: list[str] = []
    for raw in lyrics.splitlines():
        line = raw.strip()
        if not line:
            continue
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
    return lines


def excerpt(lyrics: str, max_chars: int | None = None) -> str:
    """Deduplicated opening of a lyric, cut on a line boundary."""
    limit = settings.lyrics_max_chars if max_chars is None else max_chars
    kept: list[str] = []
    total = 0
    for line in _unique_lines(lyrics):
        if total + len(line) + 1 > limit:
            break
        kept.append(line)
        total += len(line) + 1
    return "\n".join(kept)


async def fetch_lyrics(track_name: str, artists: list[str]) -> str | None:
    """Excerpt for a track, or None for instrumentals, misses and failures."""
    if not settings.lyrics_enabled:
        return None
    track = (track_name or "").strip()
    artist = (artists[0] if artists else "").strip()
    if not track or not artist:
        return None

    key = (track.casefold(), artist.casefold())
    cached = _cache.get(key)
    if cached and cached[0] > time.time():
        return cached[1]

    url = f"{settings.lrclib_base_url.rstrip('/')}/api/get"
    try:
        async with httpx.AsyncClient(
            timeout=settings.lyrics_timeout_seconds
        ) as http:
            response = await http.get(
                url,
                params={"artist_name": artist, "track_name": track},
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
        if response.status_code != 200:
            logger.info(
                "LRCLIB miss track=%s artist=%s status=%s",
                track,
                artist,
                response.status_code,
            )
            result = None
        else:
            payload = response.json()
            if payload.get("instrumental"):
                result = None
            else:
                result = excerpt(payload.get("plainLyrics") or "") or None
    except Exception as exc:
        # Transient failures stay uncached so the next request can retry.
        logger.warning("LRCLIB error track=%s err=%s", track, exc)
        return None

    _cache[key] = (time.time() + _CACHE_TTL_SECONDS, result)
    return result
