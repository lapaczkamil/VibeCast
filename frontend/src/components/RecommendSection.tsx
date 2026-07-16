import { useCallback, useEffect, useState } from "react";
import { fetchRagStatus, requestRecommendations } from "../api";
import type { RagStatus, RecommendMovieItem, RecommendResponse } from "../types";

type RecommendPhase = "idle" | "loading" | "empty" | "ok" | "error";

function RecommendResult({
  movie,
  index,
}: {
  movie: RecommendMovieItem;
  index: number;
}) {
  return (
    <li
      className="movie-item recommend-item"
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
        </p>
        <p className="recommend-reason">{movie.reason}</p>
      </div>
    </li>
  );
}

export function RecommendSection() {
  const [ragStatus, setRagStatus] = useState<RagStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [phase, setPhase] = useState<RecommendPhase>("idle");
  const [results, setResults] = useState<RecommendResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <section className="dashboard-section recommend-section">
      <h2 className="section-title">For your vibe</h2>
      <p className="recommend-hint">
        Movies picked from your listening mood — now playing, recent tracks, and
        top artists.
      </p>

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

      <div className="recommend-actions">
        <button
          type="button"
          className="cta cta--primary recommend-button"
          disabled={phase === "loading" || !canRecommend}
          onClick={() => void runRecommend()}
        >
          {phase === "loading" ? "Finding picks…" : "Recommend movies"}
        </button>
      </div>

      {phase === "idle" && !results ? (
        <p className="recommend-idle">
          Press the button when you are ready for a short list of films.
        </p>
      ) : null}

      {phase === "loading" ? (
        <p className="status-message section-status">Matching movies to your vibe…</p>
      ) : null}

      {phase === "error" && error ? (
        <p className="status-message status-message--error" role="alert">
          {error}
        </p>
      ) : null}

      {phase === "empty" ? (
        <p className="empty-state">No recommendations returned. Try again.</p>
      ) : null}

      {phase === "ok" && results ? (
        <>
          {results.mood_summary ? (
            <p className="recommend-mood">{results.mood_summary}</p>
          ) : null}
          <ol className="movie-list" aria-label="Recommended movies">
            {results.items.map((movie, index) => (
              <RecommendResult
                key={movie.tmdb_id}
                movie={movie}
                index={index}
              />
            ))}
          </ol>
        </>
      ) : null}
    </section>
  );
}
