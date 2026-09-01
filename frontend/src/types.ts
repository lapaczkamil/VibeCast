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
  image_url: string | null;
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
  image_url: string | null;
};

export type TopTracksResponse = {
  items: TopTrackItem[];
};

export type SessionResponse = {
  me: SpotifyProfile;
  recently_played: RecentlyPlayedResponse;
  top_tracks: TopTracksResponse;
  currently_playing: CurrentlyPlayingResponse;
  from_cache: boolean;
};

export type SectionState<T> = {
  status: "idle" | "loading" | "ok" | "error";
  data?: T;
  error?: string;
};

export type RateLimitStatus = {
  blocked: boolean;
  remaining_seconds: number;
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
  rating: number | null;
};

export type MovieDetail = {
  tmdb_id: number;
  title: string;
  year: string | null;
  overview: string;
  tagline: string;
  genres: string[];
  runtime: number | null;
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
  rating: number | null;
  reason: string;
  overview?: string;
};

export type RecommendResponse = {
  mood_summary: string;
  items: RecommendMovieItem[];
};

export type RecommendMoodContext = {
  track_line: string;
  mood_query: string;
  audio_profile: string | null;
  rerank_enabled: boolean;
};

export type SeedTrack = {
  id: string;
  name: string;
  artists: string[];
  image_url?: string | null;
};

export const MAX_SEEDS = 1;

export type TrackSearchItem = {
  id: string;
  name: string;
  artists: string[];
  album: string;
  spotify_url: string;
  image_url: string | null;
};

export type TrackSearchResponse = {
  items: TrackSearchItem[];
};
