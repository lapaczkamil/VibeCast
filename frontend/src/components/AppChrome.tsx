import type {
  CurrentlyPlayingResponse,
  SectionState,
  SpotifyProfile,
} from "../types";

function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

type AppChromeProps = {
  profile: SectionState<SpotifyProfile>;
  currentlyPlaying: SectionState<CurrentlyPlayingResponse>;
  loggingOut: boolean;
  onLogout: () => void;
  listeningOpen: boolean;
  onToggleListening: () => void;
  onOpenSearch: () => void;
};

export function AppChrome({
  profile,
  currentlyPlaying,
  loggingOut,
  onLogout,
  listeningOpen,
  onToggleListening,
  onOpenSearch,
}: AppChromeProps) {
  const displayName =
    profile.status === "ok" ? profile.data!.display_name : "…";
  const imageUrl =
    profile.status === "ok" ? profile.data!.image_url : null;
  const isPlaying =
    currentlyPlaying.status === "ok" &&
    currentlyPlaying.data?.is_playing === true;

  return (
    <header className="chrome">
      <div className="chrome-bar">
        <div className="chrome-left">
          <h1 className="brand brand--chrome">VibeCast</h1>
          <nav className="chrome-nav" aria-label="Primary">
            <button
              type="button"
              className={
                isPlaying
                  ? "chrome-btn chrome-btn--nav chrome-btn--listening chrome-btn--live"
                  : "chrome-btn chrome-btn--nav chrome-btn--listening"
              }
              aria-expanded={listeningOpen}
              aria-controls="listening-panel"
              onClick={onToggleListening}
            >
              Listening
              {isPlaying ? (
                <span className="chrome-live-dot" aria-hidden="true" />
              ) : null}
            </button>
            <button
              type="button"
              className="chrome-btn chrome-btn--nav"
              onClick={onOpenSearch}
            >
              Search
            </button>
          </nav>
        </div>

        <div className="chrome-right">
          <div className="profile-cluster profile-cluster--chrome">
            <div className="avatar" aria-hidden={profile.status !== "ok"}>
              {imageUrl ? (
                <img src={imageUrl} alt="" className="avatar-img" />
              ) : (
                <span className="avatar-initials">
                  {profile.status === "ok"
                    ? initialsFromName(profile.data!.display_name)
                    : "…"}
                </span>
              )}
            </div>
            <span className="profile-name">{displayName}</span>
            <button
              type="button"
              className="chrome-btn chrome-btn--logout"
              onClick={onLogout}
              disabled={loggingOut}
            >
              {loggingOut ? "Logging out…" : "Log out"}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
