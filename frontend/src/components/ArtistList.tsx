import type { TopArtistItem } from "../types";

export function ArtistList({ items }: { items: TopArtistItem[] }) {
  if (items.length === 0) {
    return (
      <p className="empty-state">
        No top artists yet. Keep listening and check back later.
      </p>
    );
  }

  return (
    <ol className="artist-list">
      {items.map((artist, index) => (
        <li
          key={artist.artist_id}
          className="artist-item"
          style={{ animationDelay: `${index * 45}ms` }}
        >
          <span className="artist-rank" aria-hidden="true">
            {index + 1}
          </span>
          {artist.image_url ? (
            <img
              src={artist.image_url}
              alt=""
              className="artist-thumb"
              width={48}
              height={48}
            />
          ) : (
            <div className="artist-thumb artist-thumb--placeholder" aria-hidden>
              {artist.name.slice(0, 1).toUpperCase()}
            </div>
          )}
          <div className="artist-main">
            <a
              href={artist.spotify_url}
              target="_blank"
              rel="noopener noreferrer"
              className="artist-name"
            >
              {artist.name}
            </a>
            {artist.genres.length > 0 && (
              <p className="artist-genres">{artist.genres.slice(0, 3).join(", ")}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
