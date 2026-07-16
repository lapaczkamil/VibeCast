import type { SectionState, SpotifyProfile } from "../types";

function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

type ProfileHeaderProps = {
  profile: SectionState<SpotifyProfile>;
  loggingOut: boolean;
  onLogout: () => void;
};

export function ProfileHeader({
  profile,
  loggingOut,
  onLogout,
}: ProfileHeaderProps) {
  const displayName =
    profile.status === "ok" ? profile.data!.display_name : "…";
  const imageUrl =
    profile.status === "ok" ? profile.data!.image_url : null;

  return (
    <header className="header">
      <h1 className="brand brand--header">VibeCast</h1>
      <div className="profile-cluster">
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
    </header>
  );
}
