import type { SectionState, SpotifyProfile } from "../types";
import type { Theme } from "../lib/theme";
import { ThemeToggle } from "./ThemeToggle";

function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

type AppChromeProps = {
  profile: SectionState<SpotifyProfile>;
  loggingOut: boolean;
  onLogout: () => void;
  onOpenListening: () => void;
  onOpenSearch: () => void;
  theme: Theme;
  onToggleTheme: () => void;
};

export function AppChrome({
  profile,
  loggingOut,
  onLogout,
  onOpenListening,
  onOpenSearch,
  theme,
  onToggleTheme,
}: AppChromeProps) {
  const displayName =
    profile.status === "ok" ? profile.data!.display_name : "…";
  const imageUrl =
    profile.status === "ok" ? profile.data!.image_url : null;

  return (
    <header className="chrome">
      <div className="chrome-bar">
        <div className="chrome-left">
          <h1 className="brand brand--chrome">VibeCast</h1>
          <nav className="chrome-nav" aria-label="Primary">
            <button
              type="button"
              className="chrome-btn chrome-btn--nav"
              onClick={onOpenListening}
            >
              Listening
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
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
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
