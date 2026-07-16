import { useCallback, useEffect, useRef, useState } from "react";
import { fetchRagStatus, requestRecommendations } from "../api";
import { nextIndex, prevIndex } from "../lib/carouselIndex";
import { tmdbPosterUrl } from "../lib/tmdbPoster";
import type { RagStatus, RecommendResponse, SeedTrack } from "../types";

type RecommendPhase = "idle" | "loading" | "empty" | "ok" | "error";

type RecommendStageProps = {
  drawerOpen: boolean;
  seeds: SeedTrack[];
  hasNowPlaying: boolean;
  isPlaying: boolean;
  onRemoveSeed: (id: string) => void;
};

const SWIPE_THRESHOLD_PX = 50;

type StackCardRole = "prev" | "current" | "next" | "hidden";

function stackCardRole(
  index: number,
  active: number,
  count: number,
): StackCardRole {
  if (count <= 0) return "hidden";
  if (index === active) return "current";
  if (count === 1) return "hidden";
  const next = nextIndex(active, count);
  const prev = prevIndex(active, count);
  if (index === next) return "next";
  // When only 2 items, next === prev — show a single peek behind.
  if (index === prev && prev !== next) return "prev";
  return "hidden";
}

export function RecommendStage({
  drawerOpen,
  seeds,
  hasNowPlaying,
  isPlaying,
  onRemoveSeed,
}: RecommendStageProps) {
  const [ragStatus, setRagStatus] = useState<RagStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [phase, setPhase] = useState<RecommendPhase>("idle");
  const [results, setResults] = useState<RecommendResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const touchStartX = useRef<number | null>(null);

  useEffect(() => {
    void fetchRagStatus()
      .then((status) => {
        setRagStatus(status);
        setStatusError(null);
      })
      .catch(() => {
        setStatusError("Could not load recommendation status.");
      });
  }, []);

  const runRecommend = useCallback(async () => {
    setPhase("loading");
    setError(null);
    setResults(null);

    try {
      const data = await requestRecommendations(seeds);
      setResults(data);
      setActiveIndex(0);
      setPhase(data.items.length === 0 ? "empty" : "ok");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Recommendation request failed";
      setError(message);
      setPhase("error");
    }
  }, [seeds]);

  const indexReady = ragStatus?.index_ready ?? false;
  const ollamaReady = ragStatus?.ollama_reachable ?? false;
  const ragReady = indexReady && ollamaReady;
  const hasSeeds = seeds.length > 0;
  const canRun = ragReady && (hasSeeds || hasNowPlaying);

  const items = results?.items ?? [];
  const itemCount = items.length;
  const activeMovie = phase === "ok" ? items[activeIndex] : undefined;

  const goNext = useCallback(() => {
    setActiveIndex((current) => nextIndex(current, itemCount));
  }, [itemCount]);

  const goPrev = useCallback(() => {
    setActiveIndex((current) => prevIndex(current, itemCount));
  }, [itemCount]);

  useEffect(() => {
    if (drawerOpen || phase !== "ok" || itemCount === 0) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        goPrev();
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        goNext();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [drawerOpen, phase, itemCount, goNext, goPrev]);

  const onTouchStart = (event: React.TouchEvent) => {
    touchStartX.current = event.touches[0]?.clientX ?? null;
  };

  const onTouchEnd = (event: React.TouchEvent) => {
    if (touchStartX.current === null || phase !== "ok" || itemCount === 0) {
      return;
    }

    const endX = event.changedTouches[0]?.clientX;
    if (endX === undefined) {
      return;
    }

    const deltaX = endX - touchStartX.current;
    touchStartX.current = null;

    if (deltaX > SWIPE_THRESHOLD_PX) {
      goPrev();
    } else if (deltaX < -SWIPE_THRESHOLD_PX) {
      goNext();
    }
  };

  const primaryLabel =
    phase === "loading"
      ? "Matching…"
      : phase === "ok"
        ? "Run again"
        : "Recommend";

  return (
    <section className="stage" aria-label="Movie recommendations">
      <div
        className={
          phase === "ok"
            ? "stage-wash stage-wash--loaded"
            : "stage-wash"
        }
        aria-hidden="true"
      />
      <div className="stage-inner">
        {phase === "idle" || phase === "error" || phase === "empty" ? (
          <header className="stage-intro">
            <p className="stage-eyebrow">Music → Movie</p>
            <h2 className="stage-heading">Match films to the mood in your mix</h2>
            <p className="stage-lede">
              Pull seed tracks from Listening, drop in a search hit, or ride
              what's playing — then run the match.
            </p>
            <p className="stage-signal-meta">
              <span>
                Seeds: <strong>{seeds.length}/5</strong>
              </span>
            </p>
          </header>
        ) : (
          <p className="stage-eyebrow">
            {isPlaying ? "Live match" : "Matched"}
          </p>
        )}

        {statusError ? (
          <p className="status-message status-message--error" role="alert">
            {statusError}
          </p>
        ) : null}

        {ragStatus && !indexReady ? (
          <p className="recommend-hint recommend-hint--warn" role="status">
            Movie index not built yet. Pull Ollama models, then run{" "}
            <code className="recommend-code">python -m app.rag.ingest</code> on
            the server.
          </p>
        ) : null}

        {ragStatus && indexReady && !ollamaReady ? (
          <p className="recommend-hint recommend-hint--warn" role="status">
            Ollama is not reachable. Start Ollama and pull{" "}
            <code className="recommend-code">{ragStatus.chat_model}</code> and{" "}
            <code className="recommend-code">{ragStatus.embed_model}</code>.
          </p>
        ) : null}

        {ragReady && !hasSeeds && !hasNowPlaying ? (
          <p className="recommend-hint" role="status">
            Select up to 5 seed tracks in Listening, or play something on
            Spotify, to get recommendations.
          </p>
        ) : null}

        {seeds.length > 0 ? (
          <div className="seed-chips" aria-label="Selected seed tracks">
            {seeds.map((track) => (
              <span key={track.id} className="seed-chip">
                <span className="seed-chip-label">
                  {track.name}
                  <span className="seed-chip-artists">
                    {" "}
                    · {track.artists.join(", ")}
                  </span>
                </span>
                <button
                  type="button"
                  className="seed-chip-remove"
                  aria-label={`Remove ${track.name} from seeds`}
                  onClick={() => onRemoveSeed(track.id)}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}

        {phase === "idle" ? (
          <div className="stage-stack stage-stack--solo" aria-hidden="true">
            <div className="stage-stack-card stage-stack-card--current stage-poster stage-poster--placeholder">
              ?
            </div>
          </div>
        ) : null}

        {phase === "loading" ? (
          <>
            <div className="stage-stack stage-stack--solo" aria-hidden="true">
              <div className="stage-stack-card stage-stack-card--current stage-poster stage-poster--skeleton" />
            </div>
            <p className="status-message section-status">
            Matching the mood in your tracks…
          </p>
          </>
        ) : null}

        {phase === "error" && error ? (
          <p className="status-message status-message--error" role="alert">
            {error}
          </p>
        ) : null}

        {phase === "empty" ? (
          <p className="empty-state">No recommendations returned. Try again.</p>
        ) : null}

        {phase === "ok" && activeMovie ? (
          <>
            <div
              className="stage-feature"
              style={
                activeMovie.poster_url
                  ? {
                      ["--stage-poster" as string]: `url(${tmdbPosterUrl(activeMovie.poster_url, "w780")})`,
                    }
                  : undefined
              }
            >
              <div className="stage-feature-glow" aria-hidden="true" />
              <div
                className="stage-carousel"
                onTouchStart={onTouchStart}
                onTouchEnd={onTouchEnd}
              >
                {itemCount > 1 ? (
                  <button
                    type="button"
                    className="stage-nav"
                    onClick={goPrev}
                    aria-label="Previous recommendation"
                  >
                    ‹
                  </button>
                ) : null}

                <div
                  className={
                    itemCount > 1
                      ? "stage-stack"
                      : "stage-stack stage-stack--solo"
                  }
                  aria-live="polite"
                >
                  {items.map((movie, index) => {
                    const role = stackCardRole(index, activeIndex, itemCount);
                    const poster = tmdbPosterUrl(movie.poster_url, "w780");
                    const posterSrcSet = poster
                      ? `${tmdbPosterUrl(movie.poster_url, "w500")} 500w, ${poster} 780w`
                      : undefined;
                    return (
                      <div
                        key={movie.tmdb_id}
                        className={`stage-stack-card stage-stack-card--${role}`}
                        aria-hidden={role !== "current"}
                      >
                        {poster ? (
                          <img
                            className="stage-poster"
                            src={poster}
                            srcSet={posterSrcSet}
                            sizes="(max-width: 640px) 55vw, 22rem"
                            alt=""
                            width={390}
                            height={585}
                            draggable={false}
                            loading={role === "current" ? "eager" : "lazy"}
                            decoding="async"
                          />
                        ) : (
                          <div
                            className="stage-poster stage-poster--placeholder"
                            aria-hidden="true"
                          >
                            ?
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {itemCount > 1 ? (
                  <button
                    type="button"
                    className="stage-nav"
                    onClick={goNext}
                    aria-label="Next recommendation"
                  >
                    ›
                  </button>
                ) : null}
              </div>
            </div>

            <div key={activeMovie.tmdb_id} className="stage-copy">
              <div className="stage-copy-meta">
                {itemCount > 1 ? (
                  <span className="stage-chip">
                    {activeIndex + 1} / {itemCount}
                  </span>
                ) : null}
                {activeMovie.year ? (
                  <span className="stage-chip stage-chip--muted">
                    {activeMovie.year}
                  </span>
                ) : null}
              </div>
              <h2 className="stage-title">{activeMovie.title}</h2>
              {results?.mood_summary ? (
                <p className="stage-mood">{results.mood_summary}</p>
              ) : null}
              <p className="stage-reason">{activeMovie.reason}</p>
            </div>

            {itemCount > 1 ? (
              <div
                className="stage-dots"
                role="tablist"
                aria-label="Recommendation position"
              >
                {items.map((movie, index) => (
                  <button
                    key={movie.tmdb_id}
                    type="button"
                    className={
                      index === activeIndex
                        ? "stage-dot stage-dot--active"
                        : "stage-dot"
                    }
                    role="tab"
                    aria-selected={index === activeIndex}
                    aria-label={`Recommendation ${index + 1} of ${itemCount}`}
                    onClick={() => setActiveIndex(index)}
                  />
                ))}
              </div>
            ) : null}
          </>
        ) : null}

        <button
          type="button"
          className="cta cta--primary recommend-button"
          disabled={phase === "loading" || !canRun}
          onClick={() => void runRecommend()}
        >
          {primaryLabel}
        </button>
      </div>
    </section>
  );
}
