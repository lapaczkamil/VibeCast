from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.config import settings
from app.spotify import oauth

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
