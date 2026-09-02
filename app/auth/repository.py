"""Session and user storage. The only module that knows the auth schema."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from app.config import settings
from app.db import connect

SESSION_ID_BYTES = 32


@dataclass(frozen=True)
class Session:
    id: str
    user_id: str | None
    oauth_state: str | None
    last_seen: float

    @property
    def authenticated(self) -> bool:
        return self.user_id is not None


@dataclass(frozen=True)
class StoredTokens:
    access_token: str
    refresh_token: str | None
    expires_at: float | None


def _ttl_seconds() -> float:
    return settings.session_ttl_days * 86400.0


def create_session() -> Session:
    session_id = secrets.token_urlsafe(SESSION_ID_BYTES)
    now = time.time()
    with connect() as connection:
        connection.execute(
            "INSERT INTO sessions (id, user_id, oauth_state, created_at, last_seen)"
            " VALUES (?, NULL, NULL, ?, ?)",
            (session_id, now, now),
        )
    return Session(id=session_id, user_id=None, oauth_state=None, last_seen=now)


def get_session(session_id: str | None) -> Session | None:
    """Live session for an id, or None when missing or expired."""
    if not session_id:
        return None
    with connect() as connection:
        row = connection.execute(
            "SELECT id, user_id, oauth_state, last_seen FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    if time.time() - row["last_seen"] > _ttl_seconds():
        delete_session(session_id)
        return None
    return Session(
        id=row["id"],
        user_id=row["user_id"],
        oauth_state=row["oauth_state"],
        last_seen=row["last_seen"],
    )


def touch_session(session_id: str) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE sessions SET last_seen = ? WHERE id = ?", (time.time(), session_id)
        )


def set_oauth_state(session_id: str, state: str | None) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE sessions SET oauth_state = ? WHERE id = ?", (state, session_id)
        )


def delete_session(session_id: str) -> None:
    with connect() as connection:
        connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def sweep_expired() -> int:
    cutoff = time.time() - _ttl_seconds()
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM sessions WHERE last_seen < ?", (cutoff,)
        )
        return cursor.rowcount


def upsert_user(
    user_id: str,
    display_name: str | None,
    tokens: StoredTokens,
) -> None:
    """Store or refresh a user's credentials, keeping the original created_at."""
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO users (id, display_name, created_at, access_token,
                               refresh_token, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                display_name  = excluded.display_name,
                access_token  = excluded.access_token,
                refresh_token = COALESCE(excluded.refresh_token, users.refresh_token),
                expires_at    = excluded.expires_at
            """,
            (
                user_id,
                display_name,
                time.time(),
                tokens.access_token,
                tokens.refresh_token,
                tokens.expires_at,
            ),
        )


def link_user(session_id: str, user_id: str) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE sessions SET user_id = ?, oauth_state = NULL WHERE id = ?",
            (user_id, session_id),
        )


def get_tokens_for(user_id: str | None) -> StoredTokens | None:
    if not user_id:
        return None
    with connect() as connection:
        row = connection.execute(
            "SELECT access_token, refresh_token, expires_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return StoredTokens(
        access_token=row["access_token"],
        refresh_token=row["refresh_token"],
        expires_at=row["expires_at"],
    )


def save_tokens_for(user_id: str, tokens: StoredTokens) -> None:
    """Persist a refreshed access token without touching the refresh token."""
    with connect() as connection:
        connection.execute(
            """
            UPDATE users SET access_token = ?,
                             refresh_token = COALESCE(?, refresh_token),
                             expires_at = ?
            WHERE id = ?
            """,
            (tokens.access_token, tokens.refresh_token, tokens.expires_at, user_id),
        )
