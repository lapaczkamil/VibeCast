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
import { ArtistList } from "./components/ArtistList";
import { DashboardSection } from "./components/DashboardSection";
import { NowPlaying } from "./components/NowPlaying";
import { ProfileHeader } from "./components/ProfileHeader";
import { MoviesSearch } from "./components/MoviesSearch";
import { RecommendSection } from "./components/RecommendSection";
import { RecentTrackList, TopTrackList } from "./components/TrackList";
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
      setMe(loadingSection());
      setCurrentlyPlaying(loadingSection());
      setRecentlyPlayed(loadingSection());
      setTopTracks(loadingSection());
      setTopArtists(loadingSection());
    }
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
          <MoviesSearch showTitle />
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <ProfileHeader
        profile={me}
        loggingOut={loggingOut}
        onLogout={() => void handleLogout()}
      />
      <main className="shell shell--logged-in">
        <DashboardSection
          title="Now playing"
          state={currentlyPlaying}
          onRetry={() => {
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
          }}
        >
          {(data) => <NowPlaying data={data} />}
        </DashboardSection>

        <DashboardSection
          title="Recently played"
          state={recentlyPlayed}
          onRetry={() => {
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
          }}
        >
          {(data) => <RecentTrackList items={data.items} />}
        </DashboardSection>

        <DashboardSection
          title="Top tracks"
          state={topTracks}
          onRetry={() => {
            setTopTracks(loadingSection());
            void fetchTopTracks(10, "medium_term")
              .then((data) => setTopTracks({ status: "ok", data }))
              .catch((err: unknown) =>
                setTopTracks({
                  status: "error",
                  error:
                    err instanceof Error
                      ? err.message
                      : "Failed to load top tracks",
                }),
              );
          }}
        >
          {(data) => <TopTrackList items={data.items} />}
        </DashboardSection>

        <DashboardSection
          title="Top artists"
          state={topArtists}
          onRetry={() => {
            setTopArtists(loadingSection());
            void fetchTopArtists(10, "medium_term")
              .then((data) => setTopArtists({ status: "ok", data }))
              .catch((err: unknown) =>
                setTopArtists({
                  status: "error",
                  error:
                    err instanceof Error
                      ? err.message
                      : "Failed to load top artists",
                }),
              );
          }}
        >
          {(data) => <ArtistList items={data.items} />}
        </DashboardSection>

        <RecommendSection />

        <section className="dashboard-section">
          <h2 className="section-title">Movies</h2>
          <MoviesSearch />
        </section>
      </main>
    </div>
  );
}
