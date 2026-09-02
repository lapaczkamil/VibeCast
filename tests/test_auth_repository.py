import time

import pytest

from app import db
from app.auth import repository as repo
from app.auth.repository import StoredTokens


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "session_db_path", str(tmp_path / "app.db"))
    monkeypatch.setattr(repo.settings, "session_ttl_days", 30)
    db.init_db()
    yield


def _tokens(access="access-1", refresh="refresh-1", expires=None):
    return StoredTokens(access_token=access, refresh_token=refresh, expires_at=expires)


def test_new_session_is_anonymous():
    session = repo.create_session()
    assert session.user_id is None
    assert session.authenticated is False
    assert repo.get_session(session.id).id == session.id


def test_session_ids_are_unguessable_and_unique():
    ids = {repo.create_session().id for _ in range(20)}
    assert len(ids) == 20
    assert all(len(i) >= 32 for i in ids)


def test_unknown_or_missing_session_is_none():
    assert repo.get_session("nope") is None
    assert repo.get_session(None) is None
    assert repo.get_session("") is None


def test_expired_session_is_dropped(monkeypatch):
    session = repo.create_session()
    monkeypatch.setattr(repo.settings, "session_ttl_days", 0)
    assert repo.get_session(session.id) is None
    # and it is gone for good, not merely hidden
    monkeypatch.setattr(repo.settings, "session_ttl_days", 30)
    assert repo.get_session(session.id) is None


def test_touch_extends_a_session():
    session = repo.create_session()
    with db.connect() as c:
        c.execute("UPDATE sessions SET last_seen = ? WHERE id = ?",
                  (time.time() - 1000, session.id))
    repo.touch_session(session.id)
    assert repo.get_session(session.id).last_seen > time.time() - 5


def test_oauth_state_is_per_session():
    a, b = repo.create_session(), repo.create_session()
    repo.set_oauth_state(a.id, "state-a")
    repo.set_oauth_state(b.id, "state-b")
    assert repo.get_session(a.id).oauth_state == "state-a"
    assert repo.get_session(b.id).oauth_state == "state-b"


def test_linking_a_user_clears_the_oauth_state():
    session = repo.create_session()
    repo.set_oauth_state(session.id, "state")
    repo.upsert_user("u1", "Kamil", _tokens())
    repo.link_user(session.id, "u1")
    stored = repo.get_session(session.id)
    assert stored.user_id == "u1"
    assert stored.oauth_state is None
    assert stored.authenticated is True


def test_two_sessions_hold_different_users():
    a, b = repo.create_session(), repo.create_session()
    repo.upsert_user("u1", "A", _tokens("access-a", "refresh-a"))
    repo.upsert_user("u2", "B", _tokens("access-b", "refresh-b"))
    repo.link_user(a.id, "u1")
    repo.link_user(b.id, "u2")
    assert repo.get_tokens_for(repo.get_session(a.id).user_id).access_token == "access-a"
    assert repo.get_tokens_for(repo.get_session(b.id).user_id).access_token == "access-b"


def test_relogin_reuses_the_user_row():
    repo.upsert_user("u1", "Kamil", _tokens("access-1", "refresh-1"))
    repo.upsert_user("u1", "Kamil Nowy", _tokens("access-2", "refresh-2"))
    with db.connect() as c:
        assert c.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 1
    tokens = repo.get_tokens_for("u1")
    assert tokens.access_token == "access-2"


def test_a_missing_refresh_token_does_not_erase_the_stored_one():
    """Spotify omits refresh_token on refresh responses."""
    repo.upsert_user("u1", "Kamil", _tokens("access-1", "refresh-1"))
    repo.save_tokens_for("u1", _tokens("access-2", None, expires=123.0))
    tokens = repo.get_tokens_for("u1")
    assert tokens.access_token == "access-2"
    assert tokens.refresh_token == "refresh-1"
    assert tokens.expires_at == 123.0


def test_tokens_for_unknown_user_is_none():
    assert repo.get_tokens_for("ghost") is None
    assert repo.get_tokens_for(None) is None


def test_deleting_a_session_leaves_the_user():
    session = repo.create_session()
    repo.upsert_user("u1", "Kamil", _tokens())
    repo.link_user(session.id, "u1")
    repo.delete_session(session.id)
    assert repo.get_session(session.id) is None
    assert repo.get_tokens_for("u1") is not None


def test_sweep_removes_only_expired_sessions(monkeypatch):
    old, fresh = repo.create_session(), repo.create_session()
    with db.connect() as c:
        c.execute("UPDATE sessions SET last_seen = ? WHERE id = ?",
                  (time.time() - 40 * 86400, old.id))
    assert repo.sweep_expired() == 1
    assert repo.get_session(fresh.id) is not None


def test_init_db_is_idempotent():
    db.init_db()
    db.init_db()
    with db.connect() as c:
        assert c.execute("SELECT COUNT(*) c FROM schema_version").fetchone()["c"] == 1


def test_schema_version_mismatch_is_loud():
    with db.connect() as c:
        c.execute("UPDATE schema_version SET version = 999")
    with pytest.raises(RuntimeError, match="schema is version 999"):
        db.init_db()
