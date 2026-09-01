from app.rag.ollama_client import (
    prepare_document_text,
    prepare_query_text,
    QWEN3_QUERY_TASK,
)


def test_prepare_document_text_nomic():
    assert (
        prepare_document_text("Fight Club", model="nomic-embed-text")
        == "search_document: Fight Club"
    )


def test_prepare_query_text_nomic():
    assert (
        prepare_query_text("dark synthwave", model="nomic-embed-text:latest")
        == "search_query: dark synthwave"
    )


def test_prepare_document_text_qwen3_unchanged():
    doc = "Fight Club (1999)\nGenres: Drama\nOverview: ..."
    assert prepare_document_text(doc, model="qwen3-embedding:0.6b") == doc


def test_prepare_query_text_qwen3_adds_instruct():
    query = "Now: Track by Artist"
    prepared = prepare_query_text(query, model="qwen3-embedding:0.6b")
    assert prepared.startswith(f"Instruct: {QWEN3_QUERY_TASK}\nQuery:")
    assert prepared.endswith(query)


def test_prepare_texts_passthrough_for_unknown_model():
    assert prepare_document_text("doc", model="llama3.2") == "doc"
    assert prepare_query_text("query", model="llama3.2") == "query"


def test_embed_uses_one_batched_request():
    import respx
    from httpx import Response

    from app.rag.ollama_client import embed_documents

    with respx.mock:
        route = respx.post("http://127.0.0.1:11434/api/embed").mock(
            return_value=Response(200, json={"embeddings": [[0.1], [0.2], [0.3]]})
        )
        result = embed_documents(["a", "b", "c"])

    assert result == [[0.1], [0.2], [0.3]]
    assert route.call_count == 1  # not one call per document
    import json as _json

    assert _json.loads(route.calls[0].request.content)["input"] == ["a", "b", "c"]


def test_embed_query_returns_a_single_vector():
    import respx
    from httpx import Response

    from app.rag.ollama_client import embed_query

    with respx.mock:
        respx.post("http://127.0.0.1:11434/api/embed").mock(
            return_value=Response(200, json={"embeddings": [[0.4, 0.5]]})
        )
        assert embed_query("mood") == [0.4, 0.5]


def test_embed_of_nothing_skips_the_request():
    import respx

    from app.rag.ollama_client import embed_documents

    with respx.mock:
        route = respx.post("http://127.0.0.1:11434/api/embed")
        assert embed_documents([]) == []
        assert route.call_count == 0


def test_short_embedding_batch_is_an_error():
    import pytest
    import respx
    from httpx import Response

    from app.rag.ollama_client import embed_documents

    with respx.mock:
        respx.post("http://127.0.0.1:11434/api/embed").mock(
            return_value=Response(200, json={"embeddings": [[0.1]]})
        )
        with pytest.raises(RuntimeError, match="1 embeddings for 3 inputs"):
            embed_documents(["a", "b", "c"])
