from typing import Any

import chromadb

from app.config import settings

_client = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.rag_chroma_path)
    return _client


# Every embedding model here is trained for cosine; Chroma defaults to l2.
COLLECTION_CONFIG = {"hnsw": {"space": "cosine"}}


def get_collection():
    """The only place a collection is created, so the metric cannot drift.

    Index configuration is immutable once written, and get_or_create silently
    returns an existing collection unchanged -- so a second creation site that
    forgets the config bakes in the default and nothing ever corrects it.
    """
    return _get_client().get_or_create_collection(
        name=settings.rag_collection,
        configuration=COLLECTION_CONFIG,
    )


def upsert_movies(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> None:
    collection = get_collection()
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )


def get_all_documents() -> tuple[list[str], list[dict[str, Any]]]:
    """Every indexed document, for building the lexical index."""
    result = get_collection().get(include=["documents", "metadatas"])
    return result.get("documents") or [], result.get("metadatas") or []


def query_movies(
    embedding: list[float],
    n_results: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    collection = get_collection()
    result = collection.query(
        query_embeddings=[embedding],
        n_results=n_results,
        include=["documents", "metadatas"],
    )
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    return documents, metadatas


def count_movies() -> int:
    return get_collection().count()


def reset_collection() -> None:
    try:
        _get_client().delete_collection(name=settings.rag_collection)
    except Exception:
        # Collection may not exist yet
        pass
    get_collection()
