import pytest
from fastapi import Depends, FastAPI, Response
from fastapi.testclient import TestClient

from app import db
from app.auth import repository as repo
from app.auth.dependencies import (
    clear_session_cookie,
    current_session,
    require_user,
)
from app.auth.repository import Session, StoredTokens
from app.config import settings


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "session_db_path", str(tmp_path / "app.db"))
    db.init_db()
    yield


@pytest.fixture
def client():
    app = FastAPI()

    @app.get("/open")
    def open_route(session: Session = Depends(current_session)):
        return {"id": session.id, "user": session.user_id}

    @app.get("/protected")
    def protected(session: Session = Depends(require_user)):
        return {"user": session.user_id}

    @app.post("/leave")
    def leave(response: Response, session: Session = Depends(current_session)):
        repo.delete_session(session.id)
        clear_session_cookie(response)
        return {"ok": True}

    return TestClient(app)


def test_first_visit_issues_a_cookie(client):
    response = client.get("/open")
    assert response.status_code == 200
    assert settings.session_cookie_name in response.cookies


def test_cookie_is_httponly_and_lax(client):
    header = client.get("/open").headers["set-cookie"]
    assert "HttpOnly" in header
    assert "SameSite=lax" in header.replace("samesite", "SameSite")


def test_same_cookie_keeps_the_same_session(client):
    first = client.get("/open").json()["id"]
    assert client.get("/open").json()["id"] == first


def test_unknown_cookie_gets_a_new_session(client):
    client.cookies.set(settings.session_cookie_name, "forged-value")
    body = client.get("/open").json()
    assert body["id"] != "forged-value"
    assert body["user"] is None


def test_protected_route_rejects_anonymous(client):
    assert client.get("/protected").status_code == 401


def test_protected_route_accepts_a_linked_session(client):
    session_id = client.get("/open").json()["id"]
    repo.upsert_user("u1", "Kamil", StoredTokens("access", "refresh", None))
    repo.link_user(session_id, "u1")
    assert client.get("/protected").json() == {"user": "u1"}


def test_two_clients_get_independent_sessions(client):
    other = TestClient(client.app)
    first = client.get("/open").json()["id"]
    second = other.get("/open").json()["id"]
    assert first != second

    repo.upsert_user("u1", "A", StoredTokens("access-a", None, None))
    repo.upsert_user("u2", "B", StoredTokens("access-b", None, None))
    repo.link_user(first, "u1")
    repo.link_user(second, "u2")

    assert client.get("/protected").json() == {"user": "u1"}
    assert other.get("/protected").json() == {"user": "u2"}


def test_logout_drops_the_session(client):
    client.get("/open")
    client.post("/leave")
    client.cookies.clear()
    assert client.get("/protected").status_code == 401
