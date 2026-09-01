from typing import Any

import chromadb

from app.config import settings

_client = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.rag_chroma_path)
    return _client


def get_collection():
    return _get_client().get_or_create_collection(name=settings.rag_collection, metadata={"hnsw:space": "cosine"})


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
    client = _get_client()
    name = settings.rag_collection
    try:
        client.delete_collection(name=name)
    except Exception:
        # Collection may not exist yet
        pass
    client.get_or_create_collection(name=name)
