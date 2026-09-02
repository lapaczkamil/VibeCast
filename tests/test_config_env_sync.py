"""Keeps .env.example honest: it is the only documentation of the knobs."""

from pathlib import Path

from app.config import Settings

ENV_EXAMPLE = Path(".env.example")
SECRETS = {
    "SPOTIFY_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET",
    "OPENAI_API_KEY",
    "TMDB_API_KEY",
}


def _example_entries() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            entries[key.strip()] = value.strip()
    return entries


def _as_env_value(default) -> str:
    if default is True:
        return "true"
    if default is False:
        return "false"
    if default is None:
        return ""
    return str(default)


def test_every_setting_is_documented():
    documented = set(_example_entries())
    expected = {name.upper() for name in Settings.model_fields}
    assert expected - documented == set(), "add these to .env.example"


def test_no_stale_keys_in_the_example():
    documented = set(_example_entries())
    expected = {name.upper() for name in Settings.model_fields}
    assert documented - expected == set(), "these no longer exist in Settings"


def test_documented_values_match_the_code_defaults():
    entries = _example_entries()
    drift = {
        name.upper(): (entries[name.upper()], _as_env_value(field.default))
        for name, field in Settings.model_fields.items()
        if name.upper() not in SECRETS
        and entries[name.upper()] != _as_env_value(field.default)
    }
    assert drift == {}, "example value != Settings default (key: example, default)"


def test_secrets_are_left_blank():
    entries = _example_entries()
    assert all(entries[key] == "" for key in SECRETS if key in entries)
