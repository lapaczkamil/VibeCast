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
GENRE_BOOST = 3


def genres_from_document(document: str) -> list[str]:
    for line in document.splitlines():
        if line.startswith("Genres:"):
            raw = line.removeprefix("Genres:").strip()
            if not raw:
                return []
            return [genre.strip() for genre in raw.split(",") if genre.strip()]
    return []


def _genre_matches(candidate_genre: str, affinity_genre: str) -> bool:
    candidate = candidate_genre.casefold()
    affinity = affinity_genre.casefold()
    return candidate == affinity or candidate in affinity or affinity in candidate


def _count_matching_genres(candidate_genres: list[str], affinity_genres: set[str]) -> int:
    matches = 0
    for candidate_genre in candidate_genres:
        for affinity_genre in affinity_genres:
            if _genre_matches(candidate_genre, affinity_genre):
                matches += 1
                break
    return matches


def _affinity_boost(candidate_genres: list[str], features: AudioFeatures) -> int:
    boost = 0

    if features.energy is not None and features.energy > ENERGY_THRESHOLD:
        boost += GENRE_BOOST * _count_matching_genres(candidate_genres, HIGH_ENERGY_GENRES)

    if features.valence is not None and features.valence < LOW_VALENCE_THRESHOLD:
        boost += GENRE_BOOST * _count_matching_genres(candidate_genres, LOW_VALENCE_GENRES)

    if features.valence is not None and features.valence > HIGH_VALENCE_THRESHOLD:
        boost += GENRE_BOOST * _count_matching_genres(candidate_genres, HIGH_VALENCE_GENRES)

    if features.acousticness is not None and features.acousticness > ACOUSTICNESS_THRESHOLD:
        boost += GENRE_BOOST * _count_matching_genres(candidate_genres, HIGH_ACOUSTIC_GENRES)

    if features.danceability is not None and features.danceability > DANCEABILITY_THRESHOLD:
        boost += GENRE_BOOST * _count_matching_genres(candidate_genres, HIGH_DANCE_GENRES)

    return boost


def rerank_candidates(
    documents: list[str],
    metadatas: list[dict],
    features: AudioFeatures,
    keep: int = 8,
) -> tuple[list[str], list[dict]]:
    scored: list[tuple[float, int, str, dict]] = []
    total = len(documents)

    for index, (document, metadata) in enumerate(zip(documents, metadatas)):
        base = total - index
        genres = genres_from_document(document)
        score = base + _affinity_boost(genres, features)
        scored.append((score, index, document, metadata))

    scored.sort(key=lambda item: (-item[0], item[1]))

    selected = scored[:keep]
    out_docs = [document for _, _, document, _ in selected]
    out_metas = [metadata for _, _, _, metadata in selected]
    return out_docs, out_metas
