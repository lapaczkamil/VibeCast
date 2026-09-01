from app.reccobeats.schemas import AudioFeatures

HIGH_ENERGY_GENRES = {"Action", "Adventure", "Thriller", "Science Fiction"}
LOW_VALENCE_GENRES = {"Drama", "Horror", "Crime", "War"}
HIGH_VALENCE_GENRES = {"Comedy", "Romance", "Family", "Animation"}
HIGH_ACOUSTIC_GENRES = {"Documentary", "Drama", "Music", "History"}
HIGH_DANCE_GENRES = {"Music", "Comedy", "Romance"}

ENERGY_THRESHOLD = 0.65
LOW_VALENCE_THRESHOLD = 0.35
HIGH_VALENCE_THRESHOLD = 0.65
ACOUSTICNESS_THRESHOLD = 0.55
DANCEABILITY_THRESHOLD = 0.65

# Share of the final score owned by the audio rules; the rest is the vector
# ranking from Chroma. Keep below 0.5 so retrieval stays the primary signal.
AUDIO_WEIGHT = 0.4

# Floor for the purity multiplier: off-mood genres dilute a match but never
# cancel it, so a partial fit still beats no fit at all.
PURITY_FLOOR = 0.5


def genres_from_document(document: str) -> list[str]:
    for line in document.splitlines():
        if line.startswith("Genres:"):
            raw = line.removeprefix("Genres:").strip()
            if not raw:
                return []
            return [genre.strip() for genre in raw.split(",") if genre.strip()]
    return []


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _above(value: float | None, threshold: float) -> float:
    """Signal strength above a threshold, ramped 0-1 over the remaining range."""
    if value is None or value <= threshold:
        return 0.0
    return _clamp((value - threshold) / (1.0 - threshold))


def _below(value: float | None, threshold: float) -> float:
    """Signal strength below a threshold, ramped 0-1 down to zero."""
    if value is None or value >= threshold:
        return 0.0
    return _clamp((threshold - value) / threshold)


def _audio_affinity(candidate_genres: list[str], features: AudioFeatures) -> float:
    """How well a movie's genres fit the active audio dimensions, 0-1.

    Each dimension counts at most once, so genre count alone cannot inflate a
    score, while a movie that matches several active dimensions scores above
    one that only matches a single dimension.
    """
    dimensions = (
        (_above(features.energy, ENERGY_THRESHOLD), HIGH_ENERGY_GENRES),
        (_below(features.valence, LOW_VALENCE_THRESHOLD), LOW_VALENCE_GENRES),
        (_above(features.valence, HIGH_VALENCE_THRESHOLD), HIGH_VALENCE_GENRES),
        (_above(features.acousticness, ACOUSTICNESS_THRESHOLD), HIGH_ACOUSTIC_GENRES),
        (_above(features.danceability, DANCEABILITY_THRESHOLD), HIGH_DANCE_GENRES),
    )
    active = [(strength, genres) for strength, genres in dimensions if strength > 0.0]
    candidate = list(dict.fromkeys(genre.casefold() for genre in candidate_genres))
    if not active or not candidate:
        return 0.0

    matched: set[str] = set()
    total = 0.0
    for strength, affinity_genres in active:
        affinity = {genre.casefold() for genre in affinity_genres}
        hits = {genre for genre in candidate if genre in affinity}
        if hits:
            total += strength
            matched |= hits

    dimension_score = total / len(active)
    purity = len(matched) / len(candidate)
    return dimension_score * (PURITY_FLOOR + (1.0 - PURITY_FLOOR) * purity)


def rerank_candidates(
    documents: list[str],
    metadatas: list[dict],
    features: AudioFeatures,
    keep: int = 8,
) -> tuple[list[str], list[dict]]:
    total = len(documents)
    if total == 0:
        return [], []

    scored: list[tuple[float, int, str, dict]] = []
    for index, (document, metadata) in enumerate(
        zip(documents, metadatas, strict=True)
    ):
        vector_score = (total - index) / total
        affinity = _audio_affinity(genres_from_document(document), features)
        score = (1.0 - AUDIO_WEIGHT) * vector_score + AUDIO_WEIGHT * affinity
        scored.append((score, index, document, metadata))

    scored.sort(key=lambda item: (-item[0], item[1]))

    selected = scored[:keep]
    out_docs = [document for _, _, document, _ in selected]
    out_metas = [metadata for _, _, _, metadata in selected]
    return out_docs, out_metas
