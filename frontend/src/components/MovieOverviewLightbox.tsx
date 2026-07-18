import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { fetchMovieDetail } from "../api";
import { tmdbPosterUrl } from "../lib/tmdbPoster";
import type { MovieDetail, RecommendMovieItem } from "../types";
import { TmdbLogo } from "./TmdbLogo";

type DetailStatus = "loading" | "ready" | "error";

function formatRuntime(minutes: number | null | undefined): string | null {
  if (minutes == null || minutes <= 0) return null;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h <= 0) return `${m}m`;
  if (m <= 0) return `${h}h`;
  return `${h}h ${m}m`;
}

type MovieOverviewLightboxProps = {
  movie: RecommendMovieItem;
  onClose: () => void;
};

export function MovieOverviewLightbox({
  movie,
  onClose,
}: MovieOverviewLightboxProps) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const poster = tmdbPosterUrl(movie.poster_url, "w780");
  const [status, setStatus] = useState<DetailStatus>("loading");
  const [detail, setDetail] = useState<MovieDetail | null>(null);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setDetail(null);
    void fetchMovieDetail(movie.tmdb_id)
      .then((value) => {
        if (cancelled) return;
        setDetail(value);
        setStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setDetail(null);
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [movie.tmdb_id]);

  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const displayYear =
    status === "ready" && detail ? (detail.year ?? movie.year) : movie.year;
  const genresText =
    status === "ready" && detail && detail.genres.length > 0
      ? detail.genres.join(" · ")
      : null;
  const runtimeText =
    status === "ready" && detail ? formatRuntime(detail.runtime) : null;

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="movie-lightbox" role="presentation">
      <button
        type="button"
        className="movie-lightbox-backdrop"
        aria-label="Close overview"
        onClick={onClose}
      />
      <div
        className="movie-lightbox-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <button
          ref={closeRef}
          type="button"
          className="movie-lightbox-close"
          aria-label="Close"
          onClick={onClose}
        >
          ×
        </button>

        <div className="movie-lightbox-layout">
          <div className="movie-lightbox-poster-wrap">
            {poster ? (
              <img
                className="movie-lightbox-poster"
                src={poster}
                alt=""
                width={320}
                height={480}
                draggable={false}
              />
            ) : (
              <div
                className="movie-lightbox-poster movie-lightbox-poster--empty"
                aria-hidden="true"
              >
                ?
              </div>
            )}
          </div>

          <div className="movie-lightbox-body">
            <p className="movie-lightbox-meta">
              {displayYear ? <span>{displayYear}</span> : null}
              {movie.rating != null ? (
                <span className="stage-rating">
                  ★ {movie.rating.toFixed(1)}
                </span>
              ) : null}
              {genresText ? (
                <span className="movie-lightbox-genres">{genresText}</span>
              ) : null}
              {runtimeText ? <span>{runtimeText}</span> : null}
              <TmdbLogo className="tmdb-logo tmdb-logo--stage" />
            </p>
            <h2 id={titleId} className="movie-lightbox-title">
              {movie.title}
            </h2>
            {status === "loading" ? (
              <p className="movie-lightbox-overview movie-lightbox-overview--muted">
                Loading details…
              </p>
            ) : null}
            {status === "ready" && detail ? (
              <>
                {detail.tagline ? (
                  <p className="movie-lightbox-tagline">{detail.tagline}</p>
                ) : null}
                <div className="movie-lightbox-overview-scroll">
                  {detail.overview ? (
                    <p className="movie-lightbox-overview">{detail.overview}</p>
                  ) : (
                    <p className="movie-lightbox-overview movie-lightbox-overview--empty">
                      No overview.
                    </p>
                  )}
                </div>
              </>
            ) : null}
            {status === "error" ? (
              <div className="movie-lightbox-overview-scroll">
                <p className="movie-lightbox-overview movie-lightbox-overview--muted">
                  Live details unavailable.
                </p>
                {(movie.overview?.trim() ?? "") ? (
                  <p className="movie-lightbox-overview">{movie.overview}</p>
                ) : (
                  <p className="movie-lightbox-overview movie-lightbox-overview--empty">
                    No overview.
                  </p>
                )}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

type PosterHotspotProps = {
  children: ReactNode;
  label: string;
  onOpen: () => void;
};

/** Makes the current poster open the overview lightbox without breaking stack layout. */
export function PosterHotspot({ children, label, onOpen }: PosterHotspotProps) {
  return (
    <button
      type="button"
      className="stage-poster-hotspot"
      aria-label={label}
      onClick={onOpen}
    >
      {children}
    </button>
  );
}
