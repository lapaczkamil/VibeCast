import { useCallback, useEffect, useRef, useState } from "react";
import { fetchRagStatus, requestRecommendations } from "../api";
import { nextIndex, prevIndex } from "../lib/carouselIndex";
import type { RagStatus, RecommendResponse } from "../types";

type RecommendPhase = "idle" | "loading" | "empty" | "ok" | "error";

type RecommendStageProps = {
  drawerOpen: boolean;
};

const SWIPE_THRESHOLD_PX = 50;

export function RecommendStage({ drawerOpen }: RecommendStageProps) {
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
      const data = await requestRecommendations();
      setResults(data);
      setActiveIndex(0);
      setPhase(data.items.length === 0 ? "empty" : "ok");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Recommendation request failed";
      setError(message);
      setPhase("error");
    }
  }, []);

  const indexReady = ragStatus?.index_ready ?? false;
  const ollamaReady = ragStatus?.ollama_reachable ?? false;
  const canRecommend = indexReady && ollamaReady;

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
      ? "Finding picks…"
      : phase === "ok"
        ? "Match again"
        : "Recommend movies";

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
        <p className="stage-eyebrow">For your vibe</p>

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

        {phase === "idle" ? (
          <div
            className="stage-poster stage-poster--placeholder"
            aria-hidden="true"
          >
            ?
          </div>
        ) : null}

        {phase === "loading" ? (
          <>
            <div
              className="stage-poster stage-poster--skeleton"
              aria-hidden="true"
            />
            <p className="status-message section-status">
              Matching movies to your vibe…
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
              {activeMovie.poster_url ? (
                <img
                  key={activeMovie.tmdb_id}
                  className="stage-poster"
                  src={activeMovie.poster_url}
                  alt=""
                  width={200}
                  height={300}
                />
              ) : (
                <div
                  key={activeMovie.tmdb_id}
                  className="stage-poster stage-poster--placeholder"
                  aria-hidden="true"
                >
                  ?
                </div>
              )}
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

            <h2 key={activeMovie.tmdb_id} className="stage-title">
              {activeMovie.title}
            </h2>
            {activeMovie.year ? (
              <p className="stage-year">{activeMovie.year}</p>
            ) : null}
            {results?.mood_summary ? (
              <p className="stage-mood">{results.mood_summary}</p>
            ) : null}
            <p className="stage-reason">{activeMovie.reason}</p>

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
          disabled={phase === "loading" || !canRecommend}
          onClick={() => void runRecommend()}
        >
          {primaryLabel}
        </button>
      </div>
    </section>
  );
}
