import asyncio

import respx
from httpx import Response

from app.reccobeats import client as rb_client


def setup_function() -> None:
    rb_client.clear_audio_features_cache()


@respx.mock
def test_fetch_audio_features_success():
    async def run() -> None:
        respx.get("https://api.reccobeats.com/v1/audio-features").mock(
            return_value=Response(
                200,
                json={
                    "content": [
                        {
                            "id": "s1",
                            "energy": 0.8,
                            "valence": 0.2,
                            "danceability": 0.3,
                            "acousticness": 0.1,
                            "instrumentalness": 0.0,
                            "speechiness": 0.05,
                            "liveness": 0.1,
                            "tempo": 120.0,
                            "loudness": -5.0,
                            "key": 1,
                            "mode": 1,
                        }
                    ]
                },
            )
        )
        features = await rb_client.fetch_audio_features("s1")
        assert features is not None
        assert features.energy == 0.8
        assert features.valence == 0.2

    asyncio.run(run())


@respx.mock
def test_fetch_audio_features_404_returns_none():
    async def run() -> None:
        respx.get("https://api.reccobeats.com/v1/audio-features").mock(
            return_value=Response(404, json={"detail": "not found"})
        )
        assert await rb_client.fetch_audio_features("missing") is None

    asyncio.run(run())


@respx.mock
def test_fetch_audio_features_uses_cache():
    async def run() -> None:
        route = respx.get("https://api.reccobeats.com/v1/audio-features").mock(
            return_value=Response(
                200,
                json={"content": [{"energy": 0.5, "valence": 0.5, "tempo": 100.0}]},
            )
        )
        await rb_client.fetch_audio_features("cached")
        await rb_client.fetch_audio_features("cached")
        assert route.call_count == 1

    asyncio.run(run())
