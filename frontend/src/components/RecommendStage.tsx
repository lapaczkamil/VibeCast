import { useCallback, useEffect, useRef, useState } from "react";
import { fetchRagStatus, requestRecommendations } from "../api";
import { nextIndex, prevIndex } from "../lib/carouselIndex";
import {
  applyPosterPalette,
  clearPosterPalette,
  extractPosterPalette,
} from "../lib/posterPalette";
import { tmdbPosterUrl } from "../lib/tmdbPoster";
import type { RagStatus, RecommendResponse, SeedTrack } from "../types";
import { MatchDropZone } from "./MatchDropZone";
import {
  MovieOverviewLightbox,
  PosterHotspot,
} from "./MovieOverviewLightbox";
import { RecommendLoading } from "./RecommendLoading";
import { TmdbLogo } from "./TmdbLogo";

type RecommendPhase = "idle" | "loading" | "empty" | "ok" | "error";

type RecommendStageProps = {
  drawerOpen: boolean;
  seedDragging: boolean;
  seeds: SeedTrack[];
  isPlaying: boolean;
  onDropSeed: (track: SeedTrack) => void;
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
  if (index === prev && prev !== next) return "prev";
  return "hidden";
}

export function RecommendStage({
  drawerOpen,
  seedDragging,
  seeds,
  isPlaying,
  onDropSeed,
  onRemoveSeed,
}: RecommendStageProps) {
  const [ragStatus, setRagStatus] = useState<RagStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [phase, setPhase] = useState<RecommendPhase>("idle");
  const [results, setResults] = useState<RecommendResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loadingLine, setLoadingLine] = useState(0);
  const [overviewOpen, setOverviewOpen] = useState(false);
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

  useEffect(() => {
    setOverviewOpen(false);
  }, [activeIndex, phase]);

  useEffect(() => {
    if (phase !== "loading") return;
    setLoadingLine(0);
    const id = window.setInterval(() => {
      setLoadingLine((n) => n + 1);
    }, 1600);
    return () => window.clearInterval(id);
  }, [phase]);

  const runRecommend = useCallback(async () => {
    if (seeds.length === 0) return;
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
  const canRun = ragReady && hasSeeds;
  const showMatchZone =
    phase === "idle" || phase === "error" || phase === "empty";
  const showSelectedTrack = phase === "ok" || phase === "loading";

  const items = results?.items ?? [];
  const itemCount = items.length;
  const activeMovie = phase === "ok" ? items[activeIndex] : undefined;
  const activePosterUrl = activeMovie
    ? tmdbPosterUrl(activeMovie.poster_url, "w500")
    : null;

  useEffect(() => {
    if (!activePosterUrl) {
      clearPosterPalette();
      return;
    }

    let cancelled = false;
    void extractPosterPalette(activePosterUrl)
      .then((palette) => {
        if (!cancelled) applyPosterPalette(palette);
      })
      .catch(() => {
        if (!cancelled) clearPosterPalette();
      });

    return () => {
      cancelled = true;
    };
  }, [activePosterUrl]);

  useEffect(() => {
    return () => {
      clearPosterPalette();
    };
  }, []);

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
    <section
      className={seedDragging ? "stage stage--drop-target" : "stage"}
      aria-label="Movie recommendations"
    >
      <div
        className={
          phase === "ok" ? "stage-wash stage-wash--loaded" : "stage-wash"
        }
        aria-hidden="true"
      />
      <div className="stage-inner">
        {showMatchZone ? (
          <header className="stage-intro">
            <h2 className="stage-heading">Match a film to one track</h2>
            <p className="stage-lede">
              Drag a track from Listening onto the slot.
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

        {ragReady && !hasSeeds ? (
          <p className="recommend-hint" role="status">
            Drop a track into the slot to unlock recommendations.
          </p>
        ) : null}

        {showMatchZone ? (
          <MatchDropZone
            seeds={seeds}
            active={seedDragging}
            disabled={false}
            onDropSeed={onDropSeed}
            onRemoveSeed={onRemoveSeed}
          />
        ) : null}

        {showSelectedTrack ? (
          <MatchDropZone
            seeds={seeds}
            active={seedDragging}
            disabled={false}
            onDropSeed={onDropSeed}
            onRemoveSeed={onRemoveSeed}
          />
        ) : null}

        {phase === "loading" ? (
          <RecommendLoading lineIndex={loadingLine} />
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
            <div className="stage-feature stage-feature--reveal">
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
                  {activePosterUrl ? (
                    <img
                      key={activePosterUrl}
                      className="stage-ambilight"
                      src={activePosterUrl}
                      alt=""
                      aria-hidden="true"
                      draggable={false}
                      crossOrigin="anonymous"
                      decoding="async"
                    />
                  ) : null}
                  <div className="stage-ambilight-leds" aria-hidden="true" />
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
                        {role === "current" ? (
                          <PosterHotspot
                            label={`View overview for ${movie.title}`}
                            onOpen={() => setOverviewOpen(true)}
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
                                crossOrigin="anonymous"
                                loading="eager"
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
                          </PosterHotspot>
                        ) : poster ? (
                          <img
                            className="stage-poster"
                            src={poster}
                            srcSet={posterSrcSet}
                            sizes="(max-width: 640px) 55vw, 22rem"
                            alt=""
                            width={390}
                            height={585}
                            draggable={false}
                            crossOrigin="anonymous"
                            loading="lazy"
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
              <p className="stage-copy-meta">
                {itemCount > 1 ? (
                  <span>
                    {activeIndex + 1}/{itemCount}
                  </span>
                ) : null}
                {activeMovie.year ? <span>{activeMovie.year}</span> : null}
                {activeMovie.rating != null ? (
                  <span className="stage-rating" title="TMDB rating">
                    ★ {activeMovie.rating.toFixed(1)}
                  </span>
                ) : null}
                <TmdbLogo className="tmdb-logo tmdb-logo--stage" />
              </p>
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

        {overviewOpen && activeMovie ? (
          <MovieOverviewLightbox
            movie={activeMovie}
            onClose={() => setOverviewOpen(false)}
          />
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
