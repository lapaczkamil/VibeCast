import json

import pytest

from app.rag import hyde
from app.rag.hyde import (
    build_hyde_prompt,
    format_hypothetical_document,
    hypothetical_document,
    parse_hyde,
)

MOOD = "Selected tracks: Nightcall by Kavinsky\nAudio profile: calm, dark/low valence"


@pytest.fixture(autouse=True)
def _enabled(monkeypatch):
    monkeypatch.setattr(hyde.settings, "rag_hyde_enabled", True)


def _reply(**overrides) -> str:
    payload = {
        "mood_summary": "neon melancholy",
        "genres": ["Crime", "Thriller"],
        "overview": "A courier drifts through a rain-slicked city at night.",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_prompt_carries_the_mood_and_constrains_genres():
    prompt = build_hyde_prompt(MOOD)
    assert MOOD in prompt
    assert "Science Fiction" in prompt
    assert "somber" in prompt  # "dark" must not be read as horror


def test_format_matches_the_indexed_document_shape():
    assert format_hypothetical_document(["Crime", "Drama"], "A quiet story.") == (
        "Genres: Crime, Drama\nOverview: A quiet story."
    )


def test_format_falls_back_when_no_genres():
    assert format_hypothetical_document([], "A quiet story.").startswith(
        "Genres: Unknown"
    )


def test_parse_extracts_genres_overview_and_summary():
    genres, overview, summary = parse_hyde(_reply())
    assert genres == ["Crime", "Thriller"]
    assert overview.startswith("A courier")
    assert summary == "neon melancholy"


def test_parse_rejects_a_reply_without_an_overview():
    with pytest.raises(ValueError):
        parse_hyde(_reply(overview="   "))


def test_parse_drops_blank_genres():
    genres, _, _ = parse_hyde(_reply(genres=["Crime", "  ", ""]))
    assert genres == ["Crime"]


def test_generates_a_movie_shaped_query(monkeypatch):
    monkeypatch.setattr(hyde, "chat_json", lambda prompt: _reply())
    result = hypothetical_document(MOOD)
    assert result.generated is True
    assert result.query == (
        "Genres: Crime, Thriller\nOverview: A courier drifts through a rain-slicked city at night."
    )
    assert result.mood_summary == "neon melancholy"


def test_falls_back_to_the_raw_mood_when_the_model_fails(monkeypatch):
    def boom(prompt):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(hyde, "chat_json", boom)
    result = hypothetical_document(MOOD)
    assert result.generated is False
    assert result.query == MOOD


def test_falls_back_on_unparseable_json(monkeypatch):
    monkeypatch.setattr(hyde, "chat_json", lambda prompt: "not json at all")
    assert hypothetical_document(MOOD).query == MOOD


def test_disabled_skips_the_model_entirely(monkeypatch):
    monkeypatch.setattr(hyde.settings, "rag_hyde_enabled", False)
    monkeypatch.setattr(
        hyde, "chat_json", lambda prompt: pytest.fail("model must not be called")
    )
    result = hypothetical_document(MOOD)
    assert result.query == MOOD and result.generated is False


def test_prompt_includes_the_lyrics_when_present():
    prompt = build_hyde_prompt(MOOD, "I'm giving you a night call")
    assert "night call" in prompt
    assert "Do not quote it" in prompt


def test_prompt_omits_the_lyrics_block_when_absent():
    assert "Lyrics excerpt" not in build_hyde_prompt(MOOD)
    assert "Lyrics excerpt" not in build_hyde_prompt(MOOD, "")


def test_lyrics_reach_the_model(monkeypatch):
    seen: dict = {}

    def capture(prompt):
        seen["prompt"] = prompt
        return _reply()

    monkeypatch.setattr(hyde, "chat_json", capture)
    hypothetical_document(MOOD, "driving through the city at night")
    assert "driving through the city at night" in seen["prompt"]
