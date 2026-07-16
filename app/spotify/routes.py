from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.config import settings
from app.spotify import oauth
from app.spotify.client import fetch_recently_played, map_recently_played
from app.spotify.schemas import RecentlyPlayedResponse

router = APIRouter()


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
        raise HTTPException(status_code=400, detail="Spotify authorization denied")
    if not code or not state or not oauth.consume_login_state(state):
        raise HTTPException(status_code=400, detail="Invalid OAuth callback")
    try:
        token_set = await oauth.exchange_code(code)
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to exchange Spotify code") from None
    oauth.set_tokens(token_set)
    return {"authenticated": True}


@router.get("/auth/spotify/status")
async def spotify_auth_status():
    return {"authenticated": oauth.get_tokens() is not None}


@router.get("/spotify/recently-played", response_model=RecentlyPlayedResponse)
async def spotify_recently_played(limit: int = Query(default=20)):
    tokens = oauth.get_tokens()
    if tokens is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    clamped_limit = max(1, min(limit, 50))
    response = await fetch_recently_played(tokens.access_token, clamped_limit)

    if response.status_code == 401 and tokens.refresh_token:
        try:
            new_tokens = await oauth.refresh_access_token()
            oauth.set_tokens(new_tokens)
            response = await fetch_recently_played(new_tokens.access_token, clamped_limit)
        except Exception:
            oauth.clear_tokens()
            raise HTTPException(status_code=401, detail="Not authenticated") from None

    if response.status_code == 401:
        oauth.clear_tokens()
        raise HTTPException(status_code=401, detail="Not authenticated")

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Spotify API request failed")

    return RecentlyPlayedResponse(items=map_recently_played(response.json()))
