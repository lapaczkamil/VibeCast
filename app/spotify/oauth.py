import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import settings

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPE = (
    "user-read-recently-played user-read-private "
    "user-read-currently-playing user-top-read"
)

_tokens: "TokenSet | None" = None
_pending_state: str | None = None


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: float | None


def clear_tokens() -> None:
    global _tokens
    _tokens = None


def get_tokens() -> TokenSet | None:
    return _tokens


def set_tokens(token_set: TokenSet) -> None:
    global _tokens
    _tokens = token_set


def clear_pending_state() -> None:
    global _pending_state
    _pending_state = None


def create_login_state() -> str:
    global _pending_state
    state = secrets.token_urlsafe(16)
    _pending_state = state
    return state


def consume_login_state(state: str) -> bool:
    global _pending_state
    if _pending_state is not None and _pending_state == state:
        _pending_state = None
        return True
    return False


def spotify_credentials_configured() -> bool:
    return bool(settings.spotify_client_id and settings.spotify_client_secret)


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": SCOPE,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _parse_token_response(data: dict) -> TokenSet:
    expires_at = None
    if "expires_in" in data:
        expires_at = time.time() + data["expires_in"]
    return TokenSet(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_at=expires_at,
    )


async def exchange_code(code: str) -> TokenSet:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.spotify_redirect_uri,
                "client_id": settings.spotify_client_id,
                "client_secret": settings.spotify_client_secret,
            },
        )
        response.raise_for_status()
        return _parse_token_response(response.json())


async def refresh_access_token() -> TokenSet:
    tokens = get_tokens()
    if tokens is None or not tokens.refresh_token:
        raise ValueError("No refresh token available")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens.refresh_token,
                "client_id": settings.spotify_client_id,
                "client_secret": settings.spotify_client_secret,
            },
        )
        response.raise_for_status()
        token_set = _parse_token_response(response.json())
        if token_set.refresh_token is None:
            token_set.refresh_token = tokens.refresh_token
        return token_set
