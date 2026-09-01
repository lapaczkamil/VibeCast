import asyncio

import pytest
import respx
from httpx import Response

from app.lyrics import client as lyrics_client
from app.lyrics.client import clear_lyrics_cache, excerpt, fetch_lyrics

URL = "https://lrclib.net/api/get"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    clear_lyrics_cache()
    monkeypatch.setattr(lyrics_client.settings, "lyrics_enabled", True)
    monkeypatch.setattr(lyrics_client.settings, "lyrics_max_chars", 1200)
    yield
    clear_lyrics_cache()


def _payload(**overrides):
    payload = {"instrumental": False, "plainLyrics": "First line\nSecond line"}
    payload.update(overrides)
    return payload


def test_excerpt_drops_blank_and_repeated_lines():
    assert excerpt("Hook\n\nVerse\nHook\nHOOK\nBridge") == "Hook\nVerse\nBridge"


def test_excerpt_cuts_on_a_line_boundary():
    assert excerpt("aaaa\nbbbb\ncccc", max_chars=10) == "aaaa\nbbbb"


def test_excerpt_of_nothing_is_empty():
    assert excerpt("\n  \n") == ""


@respx.mock
def test_returns_excerpt_for_a_vocal_track():
    respx.get(URL).mock(return_value=Response(200, json=_payload()))
    result = asyncio.run(fetch_lyrics("Nightcall", ["Kavinsky"]))
    assert result == "First line\nSecond line"


@respx.mock
def test_returns_none_for_an_instrumental():
    respx.get(URL).mock(
        return_value=Response(200, json=_payload(instrumental=True, plainLyrics=""))
    )
    assert asyncio.run(fetch_lyrics("Avril 14th", ["Aphex Twin"])) is None


@respx.mock
def test_returns_none_when_lrclib_has_no_match():
    respx.get(URL).mock(return_value=Response(404, json={}))
    assert asyncio.run(fetch_lyrics("Unknown", ["Nobody"])) is None


@respx.mock
def test_transport_failure_is_soft_and_not_cached():
    import httpx

    route = respx.get(URL).mock(
        side_effect=[httpx.ConnectError("boom"), Response(200, json=_payload())]
    )
    assert asyncio.run(fetch_lyrics("Nightcall", ["Kavinsky"])) is None
    assert asyncio.run(fetch_lyrics("Nightcall", ["Kavinsky"])) == "First line\nSecond line"
    assert route.call_count == 2


@respx.mock
def test_repeated_lookups_hit_the_cache():
    route = respx.get(URL).mock(return_value=Response(200, json=_payload()))
    asyncio.run(fetch_lyrics("Nightcall", ["Kavinsky"]))
    asyncio.run(fetch_lyrics("nightcall", ["KAVINSKY"]))
    assert route.call_count == 1


@respx.mock
def test_a_miss_is_cached_too():
    route = respx.get(URL).mock(return_value=Response(404, json={}))
    asyncio.run(fetch_lyrics("Unknown", ["Nobody"]))
    asyncio.run(fetch_lyrics("Unknown", ["Nobody"]))
    assert route.call_count == 1


@respx.mock
def test_disabled_skips_the_request(monkeypatch):
    route = respx.get(URL).mock(return_value=Response(200, json=_payload()))
    monkeypatch.setattr(lyrics_client.settings, "lyrics_enabled", False)
    assert asyncio.run(fetch_lyrics("Nightcall", ["Kavinsky"])) is None
    assert route.call_count == 0


def test_missing_track_or_artist_short_circuits():
    assert asyncio.run(fetch_lyrics("", ["Kavinsky"])) is None
    assert asyncio.run(fetch_lyrics("Nightcall", [])) is None
