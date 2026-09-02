"""SQLite storage for sessions and Spotify credentials.

One connection per operation: SQLite is fast enough at this scale and it keeps
the code free of thread-affinity rules that FastAPI's threadpool would break.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from app.config import settings

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    display_name  TEXT,
    created_at    REAL NOT NULL,
    access_token  TEXT NOT NULL,
    refresh_token TEXT,
    expires_at    REAL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    user_id     TEXT REFERENCES users(id) ON DELETE CASCADE,
    oauth_state TEXT,
    created_at  REAL NOT NULL,
    last_seen   REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS sessions_last_seen ON sessions(last_seen);

CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
"""


def db_path() -> Path:
    return Path(settings.session_db_path)


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists()
    connection = sqlite3.connect(path, timeout=10.0)
    if fresh:
        # Credentials live here; keep it readable only by the owner.
        os.chmod(path, 0o600)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def init_db() -> None:
    """Create the schema if absent. Safe to call on every startup."""
    with connect() as connection:
        connection.executescript(_SCHEMA)
        row = connection.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
            )
        elif row["version"] != SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema is version {row['version']}, "
                f"code expects {SCHEMA_VERSION}"
            )
