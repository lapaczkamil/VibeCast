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
