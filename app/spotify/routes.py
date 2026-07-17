import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.config import settings
from app.spotify import oauth
from app.spotify import upstream as spotify_upstream
from app.spotify.client import (
    fetch_currently_playing,
    fetch_me,
    fetch_recently_played,
    fetch_search,
    fetch_top_artists,
    fetch_top_tracks,
    map_currently_playing,
    map_me,
    map_recently_played,
    map_search_tracks,
    map_top_artists,
    map_top_tracks,
)
from app.spotify.schemas import (
    CurrentlyPlayingResponse,
    RecentlyPlayedResponse,
    SessionResponse,
    SpotifyProfile,
    TopArtistsResponse,
    TopTracksResponse,
    TrackSearchResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

VALID_TIME_RANGES = frozenset({"short_term", "medium_term", "long_term"})
_session_lock = asyncio.Lock()


def _frontend_redirect(path_query: str = "/") -> RedirectResponse:
    base = settings.frontend_url.rstrip("/")
    if not path_query.startswith("/"):
        path_query = "/" + path_query
    return RedirectResponse(url=f"{base}{path_query}", status_code=302)


async def _authed_spotify(
    fetch: Callable[[str], Awaitable[httpx.Response]],
) -> httpx.Response:
    tokens = oauth.get_tokens()
    if tokens is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    response = await spotify_upstream.spotify_request(
        lambda: fetch(tokens.access_token)
    )
    if response.status_code == 401 and tokens.refresh_token:
        stale_access_token = tokens.access_token
        async with oauth._refresh_lock:
            current = oauth.get_tokens()
            if current is None or not current.refresh_token:
                oauth.clear_tokens()
                raise HTTPException(status_code=401, detail="Not authenticated")
            if current.access_token != stale_access_token:
                response = await spotify_upstream.spotify_request(
                    lambda: fetch(current.access_token)
                )
            else:
                try:
                    new_tokens = await oauth.refresh_access_token()
                    oauth.set_tokens(new_tokens)
                    response = await spotify_upstream.spotify_request(
                        lambda: fetch(new_tokens.access_token)
                    )
                except Exception:
                    oauth.clear_tokens()
                    raise HTTPException(
                        status_code=401, detail="Not authenticated"
                    ) from None
    if response.status_code == 401:
        oauth.clear_tokens()
        raise HTTPException(status_code=401, detail="Not authenticated")
    return response


def _validate_time_range(time_range: str) -> str:
    if time_range not in VALID_TIME_RANGES:
        raise HTTPException(status_code=400, detail="Invalid time_range")
    return time_range


def _spotify_upstream_error(response: httpx.Response) -> HTTPException:
    status = response.status_code
    logger.warning(
        "Spotify upstream error status=%s body=%s",
        status,
        response.text[:300],
    )
    if status == 403:
        return HTTPException(
            status_code=403,
            detail=(
                "Spotify denied access (403). In Developer Dashboard go to "
                "Settings → Users Management, add your Spotify email, then "
                "log out and log in again."
            ),
        )
    if status == 429:
        remaining = int(spotify_upstream.circuit_remaining_seconds())
        return HTTPException(
            status_code=503,
            detail=(
                f"Spotify rate limit (429) — wait about {max(remaining, 30)}s "
                "and try again."
            ),
        )
    return HTTPException(
        status_code=502,
        detail=f"Spotify API request failed (upstream {status})",
    )


def _empty_now() -> CurrentlyPlayingResponse:
    return CurrentlyPlayingResponse(is_playing=False, track=None)


def _fallback_profile() -> SpotifyProfile:
    return SpotifyProfile(
        id="unknown",
        display_name="Spotify",
        image_url=None,
        country=None,
        product=None,
    )


@router.get("/auth/spotify/login")
async def spotify_login():
    if not oauth.spotify_credentials_configured():
        raise HTTPException(status_code=503, detail="Spotify credentials not configured")
    state = oauth.create_login_state()
    return RedirectResponse(oauth.build_authorize_url(state), status_code=302)


@router.get("/callback")
async def spotify_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        return _frontend_redirect("/?auth_error=1")
    if not code or not state or not oauth.consume_login_state(state):
        return _frontend_redirect("/?auth_error=1")
    try:
        token_set = await oauth.exchange_code(code)
    except Exception:
        return _frontend_redirect("/?auth_error=1")
    oauth.set_tokens(token_set)
    return _frontend_redirect("/")


@router.get("/auth/spotify/status")
async def spotify_auth_status():
    return {"authenticated": oauth.get_tokens() is not None}


@router.post("/auth/spotify/logout")
async def spotify_logout():
    oauth.clear_tokens()
    spotify_upstream.clear_cache()
    return {"authenticated": False}


@router.get("/spotify/rate-limit")
async def spotify_rate_limit_status():
    remaining = int(spotify_upstream.circuit_remaining_seconds())
    return {
        "blocked": remaining > 0,
        "remaining_seconds": remaining,
    }


@router.get("/spotify/session", response_model=SessionResponse)
async def spotify_session(
    limit: int = Query(default=10),
    time_range: str = Query(default="medium_term"),
    refresh: bool = Query(default=False),
):
    """
    One paced session load: profile + recently played + top tracks + now playing.
    Serves from cache when fresh; `refresh=true` forces a new upstream fetch.
    """
    async with _session_lock:
        clamped_limit = max(1, min(limit, 50))
        validated_range = _validate_time_range(time_range)
        me_key = "me"
        recent_key = f"recently-played:{clamped_limit}"
        top_key = f"top-tracks:{clamped_limit}:{validated_range}"
        now_key = "currently-playing"

        if refresh:
            spotify_upstream.invalidate_keys(me_key, recent_key, top_key, now_key)

        me_cached = spotify_upstream.get_cached(me_key, spotify_upstream.TTL_ME)
        recent_cached = spotify_upstream.get_cached(
            recent_key, spotify_upstream.TTL_RECENT
        )
        top_cached = spotify_upstream.get_cached(top_key, spotify_upstream.TTL_TOP)
        now_cached = spotify_upstream.get_cached(now_key, spotify_upstream.TTL_NOW)

        if (
            me_cached is not None
            and recent_cached is not None
            and top_cached is not None
        ):
            return SessionResponse(
                me=me_cached,  # type: ignore[arg-type]
                recently_played=recent_cached,  # type: ignore[arg-type]
                top_tracks=top_cached,  # type: ignore[arg-type]
                currently_playing=now_cached  # type: ignore[arg-type]
                if now_cached is not None
                else _empty_now(),
                from_cache=True,
            )

        profile = await spotify_me()
        await asyncio.sleep(1.0)
        recent = await spotify_recently_played(clamped_limit)
        await asyncio.sleep(1.0)
        top = await spotify_top_tracks(clamped_limit, validated_range)
        await asyncio.sleep(1.0)
        try:
            now = await spotify_currently_playing()
        except HTTPException:
            now = _empty_now()

        return SessionResponse(
            me=profile,
            recently_played=recent,
            top_tracks=top,
            currently_playing=now,
            from_cache=False,
        )


@router.get("/spotify/me", response_model=SpotifyProfile)
async def spotify_me():
    cache_key = "me"
    cached = spotify_upstream.get_cached(cache_key, spotify_upstream.TTL_ME)
    if cached is not None:
        return cached
    if spotify_upstream.is_circuit_open():
        stale = spotify_upstream.get_stale(cache_key)
        if stale is not None:
            return stale
        return _fallback_profile()
    response = await _authed_spotify(fetch_me)
    if response.status_code != 200:
        stale = spotify_upstream.get_stale(cache_key)
        if stale is not None:
            return stale
        if response.status_code == 429:
            return _fallback_profile()
        raise _spotify_upstream_error(response)
    profile = map_me(response.json())
    spotify_upstream.set_cached(cache_key, profile)
    return profile


@router.get("/spotify/currently-playing", response_model=CurrentlyPlayingResponse)
async def spotify_currently_playing():
    cache_key = "currently-playing"
    cached = spotify_upstream.get_cached(cache_key, spotify_upstream.TTL_NOW)
    if cached is not None:
        return cached
    empty = _empty_now()
    if spotify_upstream.is_circuit_open():
        stale = spotify_upstream.get_stale(cache_key)
        return stale if stale is not None else empty
    response = await _authed_spotify(fetch_currently_playing)
    if response.status_code == 204 or (
        response.status_code == 200 and not response.content
    ):
        spotify_upstream.set_cached(cache_key, empty)
        return empty
    if response.status_code == 200:
        payload = map_currently_playing(response.json())
        spotify_upstream.set_cached(cache_key, payload)
        return payload
    stale = spotify_upstream.get_stale(cache_key)
    if stale is not None:
        return stale
    if response.status_code == 429:
        return empty
    raise _spotify_upstream_error(response)


@router.get("/spotify/top/tracks", response_model=TopTracksResponse)
async def spotify_top_tracks(
    limit: int = Query(default=10),
    time_range: str = Query(default="medium_term"),
):
    clamped_limit = max(1, min(limit, 50))
    validated_range = _validate_time_range(time_range)
    cache_key = f"top-tracks:{clamped_limit}:{validated_range}"
    cached = spotify_upstream.get_cached(cache_key, spotify_upstream.TTL_TOP)
    if cached is not None:
        return cached
    if spotify_upstream.is_circuit_open():
        stale = spotify_upstream.get_stale(cache_key)
        if stale is not None:
            return stale
        raise _spotify_upstream_error(
            httpx.Response(429, text="Too many requests")
        )
    response = await _authed_spotify(
        lambda token: fetch_top_tracks(token, clamped_limit, validated_range)
    )
    if response.status_code != 200:
        stale = spotify_upstream.get_stale(cache_key)
        if stale is not None:
            return stale
        raise _spotify_upstream_error(response)
    payload = TopTracksResponse(items=map_top_tracks(response.json()))
    spotify_upstream.set_cached(cache_key, payload)
    return payload


@router.get("/spotify/top/artists", response_model=TopArtistsResponse)
async def spotify_top_artists(
    limit: int = Query(default=10),
    time_range: str = Query(default="medium_term"),
):
    clamped_limit = max(1, min(limit, 50))
    validated_range = _validate_time_range(time_range)
    cache_key = f"top-artists:{clamped_limit}:{validated_range}"
    cached = spotify_upstream.get_cached(cache_key, spotify_upstream.TTL_TOP)
    if cached is not None:
        return cached
    response = await _authed_spotify(
        lambda token: fetch_top_artists(token, clamped_limit, validated_range)
    )
    if response.status_code != 200:
        stale = spotify_upstream.get_stale(cache_key)
        if stale is not None:
            return stale
        raise _spotify_upstream_error(response)
    payload = TopArtistsResponse(items=map_top_artists(response.json()))
    spotify_upstream.set_cached(cache_key, payload)
    return payload


@router.get("/spotify/recently-played", response_model=RecentlyPlayedResponse)
async def spotify_recently_played(limit: int = Query(default=20)):
    clamped_limit = max(1, min(limit, 50))
    cache_key = f"recently-played:{clamped_limit}"
    cached = spotify_upstream.get_cached(cache_key, spotify_upstream.TTL_RECENT)
    if cached is not None:
        return cached
    if spotify_upstream.is_circuit_open():
        stale = spotify_upstream.get_stale(cache_key)
        if stale is not None:
            return stale
        raise _spotify_upstream_error(
            httpx.Response(429, text="Too many requests")
        )
    response = await _authed_spotify(
        lambda token: fetch_recently_played(token, clamped_limit)
    )
    if response.status_code != 200:
        stale = spotify_upstream.get_stale(cache_key)
        if stale is not None:
            return stale
        raise _spotify_upstream_error(response)
    payload = RecentlyPlayedResponse(items=map_recently_played(response.json()))
    spotify_upstream.set_cached(cache_key, payload)
    return payload


@router.get("/spotify/search", response_model=TrackSearchResponse)
async def spotify_search(q: str = Query(...), limit: int = Query(default=10)):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query must not be blank")
    clamped_limit = max(1, min(limit, 10))
    cache_key = f"search:{query.lower()}:{clamped_limit}"
    cached = spotify_upstream.get_cached(cache_key, spotify_upstream.TTL_SEARCH)
    if cached is not None:
        return cached
    if spotify_upstream.is_circuit_open():
        raise _spotify_upstream_error(
            httpx.Response(429, text="Too many requests")
        )
    response = await _authed_spotify(
        lambda token: fetch_search(token, query, clamped_limit)
    )
    if response.status_code != 200:
        raise _spotify_upstream_error(response)
    payload = TrackSearchResponse(items=map_search_tracks(response.json()))
    spotify_upstream.set_cached(cache_key, payload)
    return payload
