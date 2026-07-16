import { useCallback, useEffect, useState } from "react";
import {
  fetchAuthStatus,
  fetchCurrentlyPlaying,
  fetchMe,
  fetchRecentlyPlayed,
  fetchTopArtists,
  fetchTopTracks,
  logoutSpotify,
  startSpotifyLogin,
} from "./api";
import { AppChrome } from "./components/AppChrome";
import { ListeningDrawer } from "./components/ListeningDrawer";
import { RecommendStage } from "./components/RecommendStage";
import { SearchDrawer } from "./components/SearchDrawer";
import type {
  CurrentlyPlayingResponse,
  RecentlyPlayedResponse,
  SectionState,
  SpotifyProfile,
  TopArtistsResponse,
  TopTracksResponse,
} from "./types";

function authErrorFromSearch(search: string): boolean {
  return new URLSearchParams(search).get("auth_error") === "1";
}

function settledSection<T>(
  result: PromiseSettledResult<T>,
  fallbackError: string,
): SectionState<T> {
  if (result.status === "fulfilled") {
    return { status: "ok", data: result.value };
  }
  const message =
    result.reason instanceof Error ? result.reason.message : fallbackError;
  return { status: "error", error: message };
}

const loadingSection = <T,>(): SectionState<T> => ({ status: "loading" });

export default function App() {
  const [authError] = useState(() =>
    authErrorFromSearch(window.location.search),
  );
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authFetchError, setAuthFetchError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [drawer, setDrawer] = useState<null | "listening" | "search">(null);

  const [me, setMe] = useState<SectionState<SpotifyProfile>>(loadingSection);
  const [currentlyPlaying, setCurrentlyPlaying] =
    useState<SectionState<CurrentlyPlayingResponse>>(loadingSection);
  const [recentlyPlayed, setRecentlyPlayed] =
    useState<SectionState<RecentlyPlayedResponse>>(loadingSection);
  const [topTracks, setTopTracks] =
    useState<SectionState<TopTracksResponse>>(loadingSection);
  const [topArtists, setTopArtists] =
    useState<SectionState<TopArtistsResponse>>(loadingSection);

  const loadDashboard = useCallback(async () => {
    setMe(loadingSection());
    setCurrentlyPlaying(loadingSection());
    setRecentlyPlayed(loadingSection());
    setTopTracks(loadingSection());
    setTopArtists(loadingSection());

    const results = await Promise.allSettled([
      fetchMe(),
      fetchCurrentlyPlaying(),
      fetchRecentlyPlayed(10),
      fetchTopTracks(10, "medium_term"),
      fetchTopArtists(10, "medium_term"),
    ]);

    setMe(settledSection(results[0], "Failed to load profile"));
    setCurrentlyPlaying(
      settledSection(results[1], "Failed to load now playing"),
    );
    setRecentlyPlayed(
      settledSection(results[2], "Failed to load recently played"),
    );
    setTopTracks(settledSection(results[3], "Failed to load top tracks"));
    setTopArtists(settledSection(results[4], "Failed to load top artists"));
  }, []);

  const loadAuth = useCallback(async () => {
    setAuthLoading(true);
    setAuthFetchError(null);

    try {
      const status = await fetchAuthStatus();
      setAuthenticated(status.authenticated);
      if (status.authenticated) {
        void loadDashboard();
      }
    } catch {
      setAuthFetchError("Could not reach VibeCast. Is the backend running?");
      setAuthenticated(null);
    } finally {
      setAuthLoading(false);
    }
  }, [loadDashboard]);

  const handleLogout = useCallback(async () => {
    setLoggingOut(true);
    try {
      await logoutSpotify();
    } catch {
      // Still return to logged-out UI if the session was cleared server-side.
    } finally {
      setLoggingOut(false);
      setAuthenticated(false);
      setDrawer(null);
      setMe(loadingSection());
      setCurrentlyPlaying(loadingSection());
      setRecentlyPlayed(loadingSection());
      setTopTracks(loadingSection());
      setTopArtists(loadingSection());
    }
  }, []);

  const closeDrawer = useCallback(() => setDrawer(null), []);

  const retryCurrentlyPlaying = useCallback(() => {
    setCurrentlyPlaying(loadingSection());
    void fetchCurrentlyPlaying()
      .then((data) => setCurrentlyPlaying({ status: "ok", data }))
      .catch((err: unknown) =>
        setCurrentlyPlaying({
          status: "error",
          error:
            err instanceof Error
              ? err.message
              : "Failed to load now playing",
        }),
      );
  }, []);

  const retryRecentlyPlayed = useCallback(() => {
    setRecentlyPlayed(loadingSection());
    void fetchRecentlyPlayed(10)
      .then((data) => setRecentlyPlayed({ status: "ok", data }))
      .catch((err: unknown) =>
        setRecentlyPlayed({
          status: "error",
          error:
            err instanceof Error
              ? err.message
              : "Failed to load recently played",
        }),
      );
  }, []);

  const retryTopTracks = useCallback(() => {
    setTopTracks(loadingSection());
    void fetchTopTracks(10, "medium_term")
      .then((data) => setTopTracks({ status: "ok", data }))
      .catch((err: unknown) =>
        setTopTracks({
          status: "error",
          error:
            err instanceof Error ? err.message : "Failed to load top tracks",
        }),
      );
  }, []);

  const retryTopArtists = useCallback(() => {
    setTopArtists(loadingSection());
    void fetchTopArtists(10, "medium_term")
      .then((data) => setTopArtists({ status: "ok", data }))
      .catch((err: unknown) =>
        setTopArtists({
          status: "error",
          error:
            err instanceof Error ? err.message : "Failed to load top artists",
        }),
      );
  }, []);

  useEffect(() => {
    if (authError) {
      const url = new URL(window.location.href);
      url.searchParams.delete("auth_error");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
    void loadAuth();
  }, [authError, loadAuth]);

  if (authLoading) {
    return (
      <div className="app">
        <main className="shell shell--center">
          <p className="status-message">Tuning in…</p>
        </main>
      </div>
    );
  }

  if (authFetchError) {
    return (
      <div className="app">
        <main className="shell shell--center">
          <p className="status-message status-message--error">{authFetchError}</p>
          <button type="button" className="cta cta--ghost" onClick={loadAuth}>
            Try again
          </button>
        </main>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="app">
        <main className="shell shell--landing">
          <h1 className="brand brand--hero">VibeCast</h1>
          <p className="subtitle">
            Movies matched to the mood of your music.
          </p>
          {authError && (
            <p className="auth-error" role="alert">
              Spotify login did not complete. Please try again.
            </p>
          )}
          <button
            type="button"
            className="cta cta--primary"
            onClick={startSpotifyLogin}
          >
            Log in with Spotify
          </button>
        </main>
      </div>
    );
  }

  return (
    <div className="app app--stage">
      <AppChrome
        profile={me}
        loggingOut={loggingOut}
        onLogout={() => void handleLogout()}
        onOpenListening={() => setDrawer("listening")}
        onOpenSearch={() => setDrawer("search")}
      />
      <main className="shell shell--stage">
        <RecommendStage drawerOpen={drawer !== null} />
      </main>
      <ListeningDrawer
        open={drawer === "listening"}
        onClose={closeDrawer}
        currentlyPlaying={currentlyPlaying}
        recentlyPlayed={recentlyPlayed}
        topTracks={topTracks}
        topArtists={topArtists}
        onRetryCurrentlyPlaying={retryCurrentlyPlaying}
        onRetryRecentlyPlayed={retryRecentlyPlayed}
        onRetryTopTracks={retryTopTracks}
        onRetryTopArtists={retryTopArtists}
      />
      <SearchDrawer open={drawer === "search"} onClose={closeDrawer} />
    </div>
  );
}
