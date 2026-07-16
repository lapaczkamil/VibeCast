import type { SectionState, SpotifyProfile } from "../types";
import { ComingSoonButton } from "./ComingSoonButton";

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
};

export function AppChrome({
  profile,
  loggingOut,
  onLogout,
  onOpenListening,
  onOpenSearch,
}: AppChromeProps) {
  const displayName =
    profile.status === "ok" ? profile.data!.display_name : "…";
  const imageUrl =
    profile.status === "ok" ? profile.data!.image_url : null;

  return (
    <header className="chrome">
      <h1 className="brand brand--chrome">VibeCast</h1>
      <div className="chrome-actions">
        <button
          type="button"
          className="chrome-btn"
          onClick={onOpenListening}
        >
          Listening
        </button>
        <button type="button" className="chrome-btn" onClick={onOpenSearch}>
          Search
        </button>
        <ComingSoonButton label="Watchlists" />
        <ComingSoonButton label="Share vibe" />
        <ComingSoonButton label="History" />
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
            className="cta cta--ghost cta--logout"
            onClick={onLogout}
            disabled={loggingOut}
          >
            {loggingOut ? "Logging out…" : "Log out"}
          </button>
        </div>
      </div>
    </header>
  );
}
