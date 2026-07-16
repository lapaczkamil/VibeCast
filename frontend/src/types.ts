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
