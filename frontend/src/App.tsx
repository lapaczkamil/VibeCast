import { useCallback, useEffect, useState } from "react";
import {
  fetchAuthStatus,
  fetchCurrentlyPlaying,
  fetchMe,
  fetchRecentlyPlayed,
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
  SeedTrack,
  SpotifyProfile,
  TopTracksResponse,
} from "./types";
import { toggleSeed } from "./lib/seeds";
import {
  applyTheme,
  getStoredTheme,
  toggleTheme,
  type Theme,
} from "./lib/theme";
import { ThemeToggle } from "./components/ThemeToggle";
import { AudioMeters } from "./components/AudioMeters";
import { NowPlayingDock } from "./components/NowPlayingDock";

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
  const [seeds, setSeeds] = useState<SeedTrack[]>([]);
  const [limitHint, setLimitHint] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>(() => getStoredTheme());

  const handleToggleTheme = useCallback(() => {
    setTheme((current) => toggleTheme(current));
  }, []);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const loadDashboard = useCallback(async () => {
    setMe(loadingSection());
    setCurrentlyPlaying(loadingSection());
    setRecentlyPlayed(loadingSection());
    setTopTracks(loadingSection());

    const results = await Promise.allSettled([
      fetchMe(),
      fetchCurrentlyPlaying(),
      fetchRecentlyPlayed(10),
      fetchTopTracks(10, "medium_term"),
    ]);

    setMe(settledSection(results[0], "Failed to load profile"));
    setCurrentlyPlaying(
      settledSection(results[1], "Failed to load now playing"),
    );
    setRecentlyPlayed(
      settledSection(results[2], "Failed to load recently played"),
    );
    setTopTracks(settledSection(results[3], "Failed to load top tracks"));
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
      setSeeds([]);
      setLimitHint(null);
    }
  }, []);

  const handleToggleSeed = useCallback((track: SeedTrack) => {
    setSeeds((current) => {
      const { seeds: next, rejected } = toggleSeed(current, track);
      if (rejected) {
        setLimitHint("You can select at most 5 seed tracks.");
      } else {
        setLimitHint(null);
      }
      return next;
    });
  }, []);

  const handleClearSeeds = useCallback(() => {
    setSeeds([]);
    setLimitHint(null);
  }, []);

  const handleRemoveSeed = useCallback((id: string) => {
    setSeeds((current) => current.filter((s) => s.id !== id));
    setLimitHint(null);
  }, []);

  const closeDrawer = useCallback(() => setDrawer(null), []);

  const refreshCurrentlyPlaying = useCallback(async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) {
      setCurrentlyPlaying(loadingSection());
    }
    try {
      const data = await fetchCurrentlyPlaying();
      setCurrentlyPlaying({ status: "ok", data });
    } catch (err: unknown) {
      if (opts?.silent) {
        // Keep last good snapshot during background polls.
        return;
      }
      setCurrentlyPlaying({
        status: "error",
        error:
          err instanceof Error ? err.message : "Failed to load now playing",
      });
    }
  }, []);

  const refreshListeningLists = useCallback(async () => {
    const results = await Promise.allSettled([
      fetchRecentlyPlayed(10),
      fetchTopTracks(10, "medium_term"),
    ]);

    if (results[0].status === "fulfilled") {
      setRecentlyPlayed({ status: "ok", data: results[0].value });
    }
    if (results[1].status === "fulfilled") {
      setTopTracks({ status: "ok", data: results[1].value });
    }
  }, []);

  const retryCurrentlyPlaying = useCallback(() => {
    void refreshCurrentlyPlaying();
  }, [refreshCurrentlyPlaying]);

  useEffect(() => {
    if (!authenticated) return;

    const NOW_PLAYING_MS = 5_000;
    const LISTENING_MS = 45_000;

    const tickNowPlaying = () => {
      if (document.visibilityState === "hidden") return;
      void refreshCurrentlyPlaying({ silent: true });
    };

    const tickListening = () => {
      if (document.visibilityState === "hidden") return;
      void refreshListeningLists();
    };

    const nowPlayingId = window.setInterval(tickNowPlaying, NOW_PLAYING_MS);
    const listeningId = window.setInterval(tickListening, LISTENING_MS);

    const onVisibility = () => {
      if (document.visibilityState !== "visible") return;
      tickNowPlaying();
      tickListening();
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      window.clearInterval(nowPlayingId);
      window.clearInterval(listeningId);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [authenticated, refreshCurrentlyPlaying, refreshListeningLists]);

  useEffect(() => {
    if (drawer !== "listening" || !authenticated) return;
    // Defer fetch until after the open animation so the first paint stays smooth.
    const id = window.setTimeout(() => {
      void refreshCurrentlyPlaying({ silent: true });
      void refreshListeningLists();
    }, 280);
    return () => window.clearTimeout(id);
  }, [drawer, authenticated, refreshCurrentlyPlaying, refreshListeningLists]);

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
        <AudioMeters active />
        <div className="theme-toggle-float">
          <ThemeToggle theme={theme} onToggle={handleToggleTheme} />
        </div>
        <main className="shell shell--center">
          <p className="status-message">Loading…</p>
        </main>
      </div>
    );
  }

  if (authFetchError) {
    return (
      <div className="app">
        <AudioMeters />
        <div className="theme-toggle-float">
          <ThemeToggle theme={theme} onToggle={handleToggleTheme} />
        </div>
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
        <AudioMeters active />
        <div className="theme-toggle-float">
          <ThemeToggle theme={theme} onToggle={handleToggleTheme} />
        </div>
        <main className="shell shell--landing">
          <h1 className="brand brand--hero">VibeCast</h1>
          <p className="subtitle">Films tuned to your signal.</p>
          <p className="landing-lede">
            Plug into Spotify. Read the mood in your tracks. Match it to cinema.
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

  const hasNowPlaying =
    currentlyPlaying.status === "ok" &&
    currentlyPlaying.data?.track != null;
  const isPlaying =
    currentlyPlaying.status === "ok" &&
    currentlyPlaying.data?.is_playing === true;

  return (
    <div className={drawer ? "app app--stage app--drawer-open" : "app app--stage"}>
      <AudioMeters active={isPlaying} />
      <AppChrome
        profile={me}
        loggingOut={loggingOut}
        onLogout={() => void handleLogout()}
        onOpenListening={() => setDrawer("listening")}
        onOpenSearch={() => setDrawer("search")}
        theme={theme}
        onToggleTheme={handleToggleTheme}
      />
      <main className="shell shell--stage">
        <RecommendStage
          drawerOpen={drawer !== null}
          seeds={seeds}
          hasNowPlaying={hasNowPlaying}
          isPlaying={isPlaying}
          onRemoveSeed={handleRemoveSeed}
        />
      </main>
      <NowPlayingDock
        currentlyPlaying={currentlyPlaying}
        onOpenListening={() => setDrawer("listening")}
      />
      <ListeningDrawer
        open={drawer === "listening"}
        onClose={closeDrawer}
        currentlyPlaying={currentlyPlaying}
        recentlyPlayed={recentlyPlayed}
        topTracks={topTracks}
        seeds={seeds}
        onToggleSeed={handleToggleSeed}
        onClearSeeds={handleClearSeeds}
        limitHint={limitHint}
        onRetryCurrentlyPlaying={retryCurrentlyPlaying}
        onRetryRecentlyPlayed={retryRecentlyPlayed}
        onRetryTopTracks={retryTopTracks}
      />
      <SearchDrawer open={drawer === "search"} onClose={closeDrawer} />
    </div>
  );
}
