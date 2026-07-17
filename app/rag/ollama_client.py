import httpx

from app.config import settings

OLLAMA_TIMEOUT = httpx.Timeout(30.0)


def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        for text in texts:
            response = client.post(
                f"{settings.ollama_base_url}/api/embeddings",
                json={"model": settings.ollama_embed_model, "prompt": text},
            )
            response.raise_for_status()
            payload = response.json()
            embeddings.append(payload["embedding"])
    return embeddings


def chat_json(prompt: str) -> str:
    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        response = client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload["message"]["content"]


async def ping_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


def ping_ollama_sync() -> bool:
    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            response = client.get(f"{settings.ollama_base_url}/api/tags")
            return response.status_code == 200
    except httpx.HTTPError:
        return False
