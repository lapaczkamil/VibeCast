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

export type MoviesStatus = {
  configured: boolean;
  reachable: boolean;
};

export type MovieItem = {
  id: number;
  title: string;
  year: string | null;
  overview: string;
  poster_url: string | null;
};

export type MovieSearchResponse = {
  query: string;
  page: number;
  total_results: number;
  items: MovieItem[];
};

export type RagStatus = {
  index_ready: boolean;
  document_count: number;
  ollama_reachable: boolean;
  embed_model: string;
  chat_model: string;
};

export type RecommendMovieItem = {
  tmdb_id: number;
  title: string;
  year: string | null;
  poster_url: string | null;
  reason: string;
};

export type RecommendResponse = {
  mood_summary: string;
  items: RecommendMovieItem[];
};
