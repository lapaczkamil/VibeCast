from app.reccobeats.schemas import AudioFeatures

# Threshold bands for 0–1 features (low / mid / high).
_LOW = 0.33
_HIGH = 0.66


def _band(value: float | None, low: float, high: float) -> str:
    if value is None:
        return "mid"
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "mid"


def _energy_phrase(band: str) -> str:
    return {
        "low": "calm",
        "mid": "balanced energy",
        "high": "high energy",
    }[band]


def _valence_phrase(band: str) -> str:
    return {
        "low": "dark/low valence",
        "mid": "emotionally mixed",
        "high": "bright/uplifting",
    }[band]


def _danceability_phrase(band: str) -> str:
    return {
        "low": "low danceability",
        "mid": "moderately rhythmic",
        "high": "danceable",
    }[band]


def _acousticness_phrase(band: str) -> str:
    return {
        "low": "electronic/produced",
        "mid": "mixed production",
        "high": "mostly acoustic",
    }[band]


def _instrumentalness_phrase(band: str) -> str | None:
    if band == "low":
        return "vocal-led"
    if band == "high":
        return "instrumental"
    return None


def _tempo_phrase(tempo: float | None) -> str | None:
    if tempo is None:
        return None
    bpm = int(tempo)
    if tempo < 90:
        return f"slow tempo (~{bpm} BPM)"
    if tempo <= 120:
        return f"moderate tempo (~{bpm} BPM)"
    return f"fast tempo (~{bpm} BPM)"


def format_audio_profile(features: AudioFeatures) -> str:
    clauses: list[str] = []

    energy_band = _band(features.energy, _LOW, _HIGH)
    if features.energy is not None:
        clauses.append(_energy_phrase(energy_band))

    valence_band = _band(features.valence, _LOW, _HIGH)
    if features.valence is not None:
        clauses.append(_valence_phrase(valence_band))

    tempo_clause = _tempo_phrase(features.tempo)
    if tempo_clause is not None:
        clauses.append(tempo_clause)

    if features.danceability is not None:
        clauses.append(_danceability_phrase(_band(features.danceability, _LOW, _HIGH)))

    if features.acousticness is not None:
        clauses.append(_acousticness_phrase(_band(features.acousticness, _LOW, _HIGH)))

    if features.instrumentalness is not None:
        instrumental = _instrumentalness_phrase(
            _band(features.instrumentalness, _LOW, _HIGH)
        )
        if instrumental is not None:
            clauses.append(instrumental)

    return ", ".join(clauses)
