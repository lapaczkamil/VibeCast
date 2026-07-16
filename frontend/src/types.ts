export type AuthStatus = {
  authenticated: boolean;
};

export type RecentlyPlayedItem = {
  played_at: string;
  track_id: string;
  name: string;
  artists: string[];
  album: string;
  spotify_url: string;
};

export type RecentlyPlayedResponse = {
  items: RecentlyPlayedItem[];
};

export type SpotifyProfile = {
  id: string;
  display_name: string;
  image_url: string | null;
  country: string | null;
  product: string | null;
};

export type PlayingTrack = {
  track_id: string;
  name: string;
  artists: string[];
  album: string;
  spotify_url: string;
  image_url: string | null;
};

export type CurrentlyPlayingResponse = {
  is_playing: boolean;
  track: PlayingTrack | null;
};

export type TopTrackItem = {
  track_id: string;
  name: string;
  artists: string[];
  album: string;
  spotify_url: string;
};

export type TopTracksResponse = {
  items: TopTrackItem[];
};

export type TopArtistItem = {
  artist_id: string;
  name: string;
  genres: string[];
  image_url: string | null;
  spotify_url: string;
};

export type TopArtistsResponse = {
  items: TopArtistItem[];
};

export type SectionState<T> = {
  status: "loading" | "ok" | "error";
  data?: T;
  error?: string;
};
