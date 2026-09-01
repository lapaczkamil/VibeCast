import type {
  AuthStatus,
  CurrentlyPlayingResponse,
  MovieDetail,
  MovieSearchResponse,
  MoviesStatus,
  RagStatus,
  RateLimitStatus,
  RecentlyPlayedResponse,
  RecommendMoodContext,
  RecommendResponse,
  SeedTrack,
  SessionResponse,
  SpotifyProfile,
  TopTracksResponse,
  TrackSearchResponse,
} from "./types";

async function errorMessageFromResponse(
  res: Response,
  fallback: string,
): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // ignore non-JSON bodies
  }
  return fallback;
}

export async function fetchAuthStatus(): Promise<AuthStatus> {
  const res = await fetch("/api/auth/spotify/status");
  if (!res.ok) {
    throw new Error("Failed to load auth status");
  }
  return res.json();
}

export async function fetchRateLimitStatus(): Promise<RateLimitStatus> {
  const res = await fetch("/api/spotify/rate-limit");
  if (!res.ok) {
    return { blocked: false, remaining_seconds: 0 };
  }
  return res.json();
}

export async function fetchSpotifySession(
  options: { limit?: number; timeRange?: string; refresh?: boolean } = {},
): Promise<SessionResponse> {
  const params = new URLSearchParams({
    limit: String(options.limit ?? 10),
    time_range: options.timeRange ?? "medium_term",
  });
  if (options.refresh) {
    params.set("refresh", "true");
  }
  const res = await fetch(`/api/spotify/session?${params}`);
  if (!res.ok) {
    throw new Error(
      await errorMessageFromResponse(res, "Failed to load Spotify session"),
    );
  }
  const data = (await res.json()) as SessionResponse;
  currentlyPlayingClientCache = {
    at: Date.now(),
    data: data.currently_playing,
  };
  return data;
}

let currentlyPlayingClientCache: {
  at: number;
  data: CurrentlyPlayingResponse;
} | null = null;

/** Align with backend TTL_NOW so StrictMode / overlapping polls don't spam Spotify. */
const CURRENTLY_PLAYING_CLIENT_TTL_MS = 20_000;

let currentlyPlayingInFlight: Promise<CurrentlyPlayingResponse> | null = null;

export async function fetchCurrentlyPlaying(): Promise<CurrentlyPlayingResponse> {
  if (
    currentlyPlayingClientCache &&
    Date.now() - currentlyPlayingClientCache.at < CURRENTLY_PLAYING_CLIENT_TTL_MS
  ) {
    return currentlyPlayingClientCache.data;
  }
  if (currentlyPlayingInFlight) {
    return currentlyPlayingInFlight;
  }

  currentlyPlayingInFlight = (async () => {
    const res = await fetch("/api/spotify/currently-playing");
    if (!res.ok) {
      throw new Error(
        await errorMessageFromResponse(res, "Failed to load currently playing"),
      );
    }
    const data = (await res.json()) as CurrentlyPlayingResponse;
    currentlyPlayingClientCache = { at: Date.now(), data };
    return data;
  })().finally(() => {
    currentlyPlayingInFlight = null;
  });

  return currentlyPlayingInFlight;
}

export async function fetchRecentlyPlayed(
  limit = 20,
): Promise<RecentlyPlayedResponse> {
  const res = await fetch(`/api/spotify/recently-played?limit=${limit}`);
  if (!res.ok) {
    throw new Error(
      await errorMessageFromResponse(res, "Failed to load recently played"),
    );
  }
  return res.json();
}

export async function fetchMe(): Promise<SpotifyProfile> {
  const res = await fetch("/api/spotify/me");
  if (!res.ok) {
    throw new Error(
      await errorMessageFromResponse(res, "Failed to load profile"),
    );
  }
  return res.json();
}

export async function fetchTopTracks(
  limit = 10,
  timeRange = "medium_term",
): Promise<TopTracksResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    time_range: timeRange,
  });
  const res = await fetch(`/api/spotify/top/tracks?${params}`);
  if (!res.ok) {
    throw new Error(
      await errorMessageFromResponse(res, "Failed to load top tracks"),
    );
  }
  return res.json();
}

export async function logoutSpotify(): Promise<AuthStatus> {
  const res = await fetch("/api/auth/spotify/logout", { method: "POST" });
  if (!res.ok) {
    throw new Error("Failed to log out");
  }
  return res.json();
}

export function startSpotifyLogin(): void {
  window.location.assign("/api/auth/spotify/login");
}

export async function fetchMoviesStatus(): Promise<MoviesStatus> {
  const res = await fetch("/api/movies/status");
  if (!res.ok) {
    throw new Error("Failed to load movies status");
  }
  return res.json();
}

const movieDetailCache = new Map<number, MovieDetail>();

export async function fetchMovieDetail(tmdbId: number): Promise<MovieDetail> {
  const cached = movieDetailCache.get(tmdbId);
  if (cached) return cached;

  const res = await fetch(`/api/movies/${tmdbId}`);
  if (!res.ok) {
    if (res.status === 503) {
      throw new Error(
        await errorMessageFromResponse(res, "TMDB API key not configured"),
      );
    }
    if (res.status === 404) {
      throw new Error(await errorMessageFromResponse(res, "Movie not found"));
    }
    if (res.status === 502) {
      throw new Error(
        await errorMessageFromResponse(res, "TMDB API request failed"),
      );
    }
    throw new Error(
      await errorMessageFromResponse(res, "Failed to load movie details"),
    );
  }
  const detail = (await res.json()) as MovieDetail;
  movieDetailCache.set(tmdbId, detail);
  return detail;
}

export async function searchMovies(
  q: string,
  page = 1,
): Promise<MovieSearchResponse> {
  const params = new URLSearchParams({
    q,
    page: String(page),
  });
  const res = await fetch(`/api/movies/search?${params}`);
  if (!res.ok) {
    if (res.status === 503) {
      throw new Error(
        await errorMessageFromResponse(
          res,
          "TMDB API key not configured",
        ),
      );
    }
    if (res.status === 502) {
      throw new Error(
        await errorMessageFromResponse(res, "TMDB API request failed"),
      );
    }
    if (res.status === 400) {
      throw new Error(
        await errorMessageFromResponse(res, "Enter a search query"),
      );
    }
    throw new Error(
      await errorMessageFromResponse(res, "Movie search failed"),
    );
  }
  return res.json();
}

export async function fetchRagStatus(): Promise<RagStatus> {
  const res = await fetch("/api/rag/status");
  if (!res.ok) {
    throw new Error("Failed to load RAG status");
  }
  return res.json();
}

export async function searchSpotifyTracks(
  q: string,
  limit = 10,
): Promise<TrackSearchResponse> {
  const params = new URLSearchParams({
    q,
    limit: String(limit),
  });
  const res = await fetch(`/api/spotify/search?${params}`);
  if (!res.ok) {
    if (res.status === 400) {
      throw new Error(
        await errorMessageFromResponse(res, "Enter a search query"),
      );
    }
    throw new Error(
      await errorMessageFromResponse(res, "Track search failed"),
    );
  }
  return res.json();
}

function recommendTrackPayload(tracks: SeedTrack[]) {
  return {
    tracks: tracks.map((track) => ({
      id: track.id,
      name: track.name,
      artists: track.artists,
    })),
  };
}

export async function fetchMoodContext(
  tracks: SeedTrack[],
): Promise<RecommendMoodContext> {
  const res = await fetch("/api/recommend/mood-context", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(recommendTrackPayload(tracks)),
  });
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error(
        await errorMessageFromResponse(res, "Not authenticated"),
      );
    }
    if (res.status === 422) {
      throw new Error(
        await errorMessageFromResponse(res, "At most 1 track allowed"),
      );
    }
    throw new Error(
      await errorMessageFromResponse(res, "Failed to load match signals"),
    );
  }
  return res.json();
}

export async function requestRecommendations(
  tracks: SeedTrack[],
): Promise<RecommendResponse> {
  const res = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(recommendTrackPayload(tracks)),
  });
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error(
        await errorMessageFromResponse(res, "Not authenticated"),
      );
    }
    if (res.status === 400) {
      throw new Error(
        await errorMessageFromResponse(
          res,
          "Select seed tracks or play something on Spotify",
        ),
      );
    }
    if (res.status === 422) {
      throw new Error(
        await errorMessageFromResponse(res, "At most 5 tracks allowed"),
      );
    }
    if (res.status === 503) {
      throw new Error(
        await errorMessageFromResponse(
          res,
          "Recommendations unavailable; check Ollama and movie index",
        ),
      );
    }
    if (res.status === 502) {
      throw new Error(
        await errorMessageFromResponse(
          res,
          "Failed to parse recommendation response",
        ),
      );
    }
    throw new Error(
      await errorMessageFromResponse(res, "Recommendation request failed"),
    );
  }
  return res.json();
}
