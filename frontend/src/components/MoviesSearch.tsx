import { useCallback, useEffect, useState, type FormEvent } from "react";
import { fetchMoviesStatus, searchMovies } from "../api";
import type { MovieItem, MovieSearchResponse } from "../types";
import { TmdbLogo } from "./TmdbLogo";

type SearchPhase = "idle" | "loading" | "empty" | "ok" | "error";

type MoviesSearchProps = {
  showTitle?: boolean;
};

function truncateOverview(text: string, maxLength = 160): string {
  const trimmed = text.trim();
  if (trimmed.length <= maxLength) return trimmed;
  return `${trimmed.slice(0, maxLength).trimEnd()}…`;
}

function MovieResult({ movie, index }: { movie: MovieItem; index: number }) {
  return (
    <li
      className="movie-item"
      style={{ animationDelay: `${index * 45}ms` }}
    >
      {movie.poster_url ? (
        <img
          className="movie-poster"
          src={movie.poster_url}
          alt=""
          width={52}
          height={78}
          loading="lazy"
        />
      ) : (
        <div className="movie-poster movie-poster--placeholder" aria-hidden="true">
          ?
        </div>
      )}
      <div className="movie-main">
        <p className="movie-title">
          {movie.title}
          {movie.year ? (
            <span className="movie-year"> ({movie.year})</span>
          ) : null}
          {movie.rating != null ? (
            <span className="movie-rating" title="TMDB rating">
              {" "}
              · ★ {movie.rating.toFixed(1)}
            </span>
          ) : null}
          <TmdbLogo className="tmdb-logo tmdb-logo--inline" />
        </p>
        {movie.overview ? (
          <p className="movie-overview">{truncateOverview(movie.overview)}</p>
        ) : (
          <p className="movie-overview movie-overview--empty">No overview.</p>
        )}
      </div>
    </li>
  );
}

export function MoviesSearch({ showTitle = false }: MoviesSearchProps) {
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<SearchPhase>("idle");
  const [results, setResults] = useState<MovieSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);

  useEffect(() => {
    void fetchMoviesStatus()
      .then((status) => setNotConfigured(!status.configured))
      .catch(() => {
        // Status is optional; search errors still surface on submit.
      });
  }, []);

  const runSearch = useCallback(async (rawQuery: string) => {
    const trimmed = rawQuery.trim();
    if (!trimmed) {
      setPhase("idle");
      setResults(null);
      setError(null);
      return;
    }

    setPhase("loading");
    setError(null);
    setResults(null);

    try {
      const data = await searchMovies(trimmed);
      setResults(data);
      setPhase(data.items.length === 0 ? "empty" : "ok");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Movie search failed";
      setError(message);
      setPhase("error");
      if (message.toLowerCase().includes("not configured")) {
        setNotConfigured(true);
      }
    }
  }, []);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    void runSearch(query);
  };

  return (
    <section className="movies-search">
      {showTitle ? <h2 className="section-title">Movies</h2> : null}
      {notConfigured ? (
        <p className="movies-hint movies-hint--warn" role="status">
          TMDB is not configured on the server. Add TMDB_API_KEY to .env to
          search movies.
        </p>
      ) : (
        <p className="movies-hint">Search TMDB for a film title.</p>
      )}
      <form className="movies-form" onSubmit={handleSubmit}>
        <input
          type="search"
          className="movies-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. Inception"
          aria-label="Movie search"
        />
        <button
          type="submit"
          className="cta cta--ghost movies-submit"
          disabled={phase === "loading"}
        >
          {phase === "loading" ? "Searching…" : "Search"}
        </button>
      </form>
      {phase === "idle" && !results ? (
        <p className="movies-idle">Enter a title and press Search.</p>
      ) : null}
      {phase === "loading" ? (
        <p className="status-message section-status">Searching movies…</p>
      ) : null}
      {phase === "error" && error ? (
        <p className="status-message status-message--error" role="alert">
          {error}
        </p>
      ) : null}
      {phase === "empty" ? (
        <p className="empty-state">No movies found for that query.</p>
      ) : null}
      {phase === "ok" && results ? (
        <ol className="movie-list" aria-label="Movie search results">
          {results.items.map((movie, index) => (
            <MovieResult key={movie.id} movie={movie} index={index} />
          ))}
        </ol>
      ) : null}
    </section>
  );
}
