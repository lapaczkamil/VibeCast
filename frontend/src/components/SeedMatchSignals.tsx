import type { RecommendMoodContext } from "../types";

type SeedMatchSignalsProps = {
  context: RecommendMoodContext | null;
  loading: boolean;
  error: string | null;
};

function profileTraits(profile: string): string[] {
  return profile
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export function SeedMatchSignals({
  context,
  loading,
  error,
}: SeedMatchSignalsProps) {
  if (loading) {
    return (
      <div className="seed-match-signals" aria-busy="true" aria-live="polite">
        <p className="seed-match-signals__title">Match signals</p>
        <p className="seed-match-signals__muted">Loading audio profile…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="seed-match-signals" role="alert">
        <p className="seed-match-signals__title">Match signals</p>
        <p className="seed-match-signals__muted">{error}</p>
      </div>
    );
  }

  if (!context) {
    return null;
  }

  const traits = context.audio_profile
    ? profileTraits(context.audio_profile)
    : [];

  return (
    <div className="seed-match-signals" aria-live="polite">
      <p className="seed-match-signals__title">Used for matching</p>

      <dl className="seed-match-signals__list">
        <div className="seed-match-signals__row">
          <dt>Track</dt>
          <dd>{context.track_line}</dd>
        </div>
        {traits.length > 0 ? (
          <div className="seed-match-signals__row">
            <dt>Audio profile</dt>
            <dd>
              <ul className="seed-match-signals__traits">
                {traits.map((trait) => (
                  <li key={trait} className="seed-match-signals__trait">
                    {trait}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        ) : (
          <div className="seed-match-signals__row">
            <dt>Audio profile</dt>
            <dd className="seed-match-signals__muted">
              Not available for this track
            </dd>
          </div>
        )}
        {context.rerank_enabled ? (
          <div className="seed-match-signals__row">
            <dt>Rerank</dt>
            <dd>Top candidates adjusted by audio features</dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}
