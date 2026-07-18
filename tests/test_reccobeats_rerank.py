from app.reccobeats.rerank import genres_from_document, rerank_candidates
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
