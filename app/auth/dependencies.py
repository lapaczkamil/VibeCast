"""Resolving the caller's session from the request cookie."""

from __future__ import annotations

import time

from fastapi import Depends, HTTPException, Request, Response

from app.auth import repository
from app.auth.repository import Session
from app.config import settings

# Writing last_seen on every request would mean a DB write per poll; the cookie
# lifetime is measured in days, so refreshing it once a minute is plenty.
TOUCH_INTERVAL_SECONDS = 60.0


def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")


def current_session(request: Request, response: Response) -> Session:
    """The caller's session, creating one when they arrive without a cookie."""
    session = repository.get_session(request.cookies.get(settings.session_cookie_name))
    if session is None:
        session = repository.create_session()
        set_session_cookie(response, session.id)
        return session
    if time.time() - session.last_seen > TOUCH_INTERVAL_SECONDS:
        repository.touch_session(session.id)
    return session


def require_user(session: Session = Depends(current_session)) -> Session:
    """Same, but rejects callers who have not linked a Spotify account."""
    if not session.authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session
