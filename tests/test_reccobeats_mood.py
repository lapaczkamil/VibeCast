from app.reccobeats.mood import format_audio_profile
from app.reccobeats.schemas import AudioFeatures


def test_format_audio_profile_high_energy_low_valence():
    features = AudioFeatures(
        energy=0.9,
        valence=0.15,
        danceability=0.2,
        acousticness=0.8,
        instrumentalness=0.1,
        tempo=92.0,
        speechiness=0.05,
        liveness=0.1,
        loudness=-8.0,
        key=5,
        mode=0,
    )
    text = format_audio_profile(features).lower()
    assert "high energy" in text or "intense" in text
    assert "dark" in text or "melancholic" in text or "low valence" in text
    assert "92" in text
    assert "acoustic" in text
