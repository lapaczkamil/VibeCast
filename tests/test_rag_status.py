from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_rag_status_shape(monkeypatch):
    monkeypatch.setattr("app.rag.routes.count_movies", lambda: 0)
    monkeypatch.setattr("app.rag.routes.ping_ollama_sync", lambda: False)
    r = client.get("/rag/status")
    assert r.status_code == 200
    body = r.json()
    assert body["index_ready"] is False
    assert body["document_count"] == 0
    assert body["ollama_reachable"] is False
    assert "embed_model" in body and "chat_model" in body
