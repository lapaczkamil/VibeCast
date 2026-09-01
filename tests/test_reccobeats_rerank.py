from app.reccobeats.rerank import (
    PURITY_FLOOR,
    _audio_affinity,
    genres_from_document,
    rerank_candidates,
)
from app.reccobeats.schemas import AudioFeatures


def test_genres_from_document():
    doc = "Fight Club (1999)\nGenres: Drama, Thriller\nOverview: ..."
    assert genres_from_document(doc) == ["Drama", "Thriller"]


def test_rerank_boosts_high_energy_action():
    docs = [
        "Calm Film\nGenres: Drama\nOverview: x",
        "Loud Film\nGenres: Action, Thriller\nOverview: y",
    ]
    metas = [{"tmdb_id": 1, "title": "Calm"}, {"tmdb_id": 2, "title": "Loud"}]
    features = AudioFeatures(energy=0.95, valence=0.5, danceability=0.4, acousticness=0.1)
    out_docs, out_metas = rerank_candidates(docs, metas, features, keep=2)
    assert out_metas[0]["tmdb_id"] == 2


def _pool(*genre_lines: str) -> tuple[list[str], list[dict]]:
    docs = [
        f"Movie {index}\nGenres: {genres}\nOverview: x"
        for index, genres in enumerate(genre_lines)
    ]
    metas = [{"tmdb_id": index, "title": f"Movie {index}"} for index in range(len(docs))]
    return docs, metas


def test_audio_rules_cannot_lift_last_candidate_above_first():
    # Worst vector match with a strong genre fit vs best vector match with none.
    docs, metas = _pool("Western", *["Western"] * 14, "Comedy, Romance, Music")
    features = AudioFeatures(valence=0.9, danceability=0.9, acousticness=0.8)
    out_docs, out_metas = rerank_candidates(docs, metas, features, keep=16)
    ranking = [meta["tmdb_id"] for meta in out_metas]
    assert ranking[0] == 0
    assert ranking.index(15) > 3  # it climbs, but cannot take over the head


def test_genre_count_does_not_inflate_affinity():
    # Both are fully high-energy; the four-tag movie must not win on count.
    docs, metas = _pool("Action", "Action, Adventure, Thriller, Science Fiction")
    features = AudioFeatures(energy=0.9)
    out_docs, out_metas = rerank_candidates(docs, metas, features, keep=2)
    assert out_metas[0]["tmdb_id"] == 0


def test_mixed_genres_score_below_focused_ones():
    features = AudioFeatures(energy=0.9)
    focused = _audio_affinity(["Action"], features)
    mixed = _audio_affinity(["Action", "Drama"], features)
    assert focused > mixed > 0.0


def test_affinity_ramps_with_distance_past_threshold():
    docs, metas = _pool("Drama", "Action")
    barely = AudioFeatures(energy=0.66)
    strongly = AudioFeatures(energy=0.99)
    assert rerank_candidates(docs, metas, barely, keep=2)[1][0]["tmdb_id"] == 0
    assert rerank_candidates(docs, metas, strongly, keep=2)[1][0]["tmdb_id"] == 1


def test_inactive_features_preserve_vector_order():
    docs, metas = _pool("Action", "Drama", "Comedy")
    features = AudioFeatures(energy=0.5, valence=0.5, danceability=0.5, acousticness=0.5)
    out_docs, out_metas = rerank_candidates(docs, metas, features, keep=3)
    assert [meta["tmdb_id"] for meta in out_metas] == [0, 1, 2]


def test_all_features_missing_preserves_vector_order():
    docs, metas = _pool("Action", "Drama")
    out_docs, out_metas = rerank_candidates(docs, metas, AudioFeatures(), keep=2)
    assert [meta["tmdb_id"] for meta in out_metas] == [0, 1]


def test_missing_genres_line_does_not_crash():
    docs = ["No genres here\nOverview: x", "Loud\nGenres: Action\nOverview: y"]
    metas = [{"tmdb_id": 0}, {"tmdb_id": 1}]
    out_docs, out_metas = rerank_candidates(docs, metas, AudioFeatures(energy=0.9), keep=2)
    assert [meta["tmdb_id"] for meta in out_metas] == [0, 1]
    assert _audio_affinity([], AudioFeatures(energy=0.9)) == 0.0


def test_empty_input_returns_empty():
    assert rerank_candidates([], [], AudioFeatures(energy=0.9)) == ([], [])


def test_matching_more_dimensions_beats_matching_one():
    # Loud and dark track: a movie that hits both moods must outrank one
    # that only hits the loud half.
    features = AudioFeatures(energy=0.95, valence=0.2)
    both = _audio_affinity(["Thriller", "Crime"], features)
    loud_only = _audio_affinity(["Action", "Thriller"], features)
    dark_only = _audio_affinity(["Drama"], features)
    assert both > loud_only > dark_only > 0.0


def test_off_mood_genres_dilute_but_do_not_cancel():
    features = AudioFeatures(energy=0.9)
    pure = _audio_affinity(["Action"], features)
    diluted = _audio_affinity(["Action", "Documentary"], features)
    assert pure > diluted >= pure * PURITY_FLOOR
