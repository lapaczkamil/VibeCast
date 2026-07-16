from collections.abc import Awaitable, Callable

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.config import settings
from app.spotify import oauth
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
    SpotifyProfile,
    TopArtistsResponse,
    TopTracksResponse,
    TrackSearchResponse,
)

router = APIRouter()

VALID_TIME_RANGES = frozenset({"short_term", "medium_term", "long_term"})


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
    response = await fetch(tokens.access_token)
    if response.status_code == 401 and tokens.refresh_token:
        stale_access_token = tokens.access_token
        async with oauth._refresh_lock:
            current = oauth.get_tokens()
            if current is None or not current.refresh_token:
                oauth.clear_tokens()
                raise HTTPException(status_code=401, detail="Not authenticated")
            if current.access_token != stale_access_token:
                response = await fetch(current.access_token)
            else:
                try:
                    new_tokens = await oauth.refresh_access_token()
                    oauth.set_tokens(new_tokens)
                    response = await fetch(new_tokens.access_token)
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
    return {"authenticated": False}


@router.get("/spotify/me", response_model=SpotifyProfile)
async def spotify_me():
    response = await _authed_spotify(fetch_me)
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Spotify API request failed")
    return map_me(response.json())


@router.get("/spotify/currently-playing", response_model=CurrentlyPlayingResponse)
async def spotify_currently_playing():
    response = await _authed_spotify(fetch_currently_playing)
    if response.status_code == 204 or (
        response.status_code == 200 and not response.content
    ):
        return CurrentlyPlayingResponse(is_playing=False, track=None)
    if response.status_code == 200:
        return map_currently_playing(response.json())
    raise HTTPException(status_code=502, detail="Spotify API request failed")


@router.get("/spotify/top/tracks", response_model=TopTracksResponse)
async def spotify_top_tracks(
    limit: int = Query(default=10),
    time_range: str = Query(default="medium_term"),
):
    clamped_limit = max(1, min(limit, 50))
    validated_range = _validate_time_range(time_range)
    response = await _authed_spotify(
        lambda token: fetch_top_tracks(token, clamped_limit, validated_range)
    )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Spotify API request failed")
    return TopTracksResponse(items=map_top_tracks(response.json()))


@router.get("/spotify/top/artists", response_model=TopArtistsResponse)
async def spotify_top_artists(
    limit: int = Query(default=10),
    time_range: str = Query(default="medium_term"),
):
    clamped_limit = max(1, min(limit, 50))
    validated_range = _validate_time_range(time_range)
    response = await _authed_spotify(
        lambda token: fetch_top_artists(token, clamped_limit, validated_range)
    )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Spotify API request failed")
    return TopArtistsResponse(items=map_top_artists(response.json()))


@router.get("/spotify/recently-played", response_model=RecentlyPlayedResponse)
async def spotify_recently_played(limit: int = Query(default=20)):
    clamped_limit = max(1, min(limit, 50))
    response = await _authed_spotify(
        lambda token: fetch_recently_played(token, clamped_limit)
    )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Spotify API request failed")
    return RecentlyPlayedResponse(items=map_recently_played(response.json()))


@router.get("/spotify/search", response_model=TrackSearchResponse)
async def spotify_search(q: str = Query(...), limit: int = Query(default=10)):
    if not q.strip():
        raise HTTPException(status_code=422, detail="Query must not be blank")
    response = await _authed_spotify(
        lambda token: fetch_search(token, q.strip(), limit)
    )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Spotify API request failed")
    return TrackSearchResponse(items=map_search_tracks(response.json()))
