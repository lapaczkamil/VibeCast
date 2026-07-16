import { Drawer } from "./Drawer";
import { DashboardSection } from "./DashboardSection";
import { NowPlaying } from "./NowPlaying";
import { ArtistList } from "./ArtistList";
import { RecentTrackList, TopTrackList } from "./TrackList";
import type {
  CurrentlyPlayingResponse,
  RecentlyPlayedResponse,
  SectionState,
  TopArtistsResponse,
  TopTracksResponse,
} from "../types";

type ListeningDrawerProps = {
  open: boolean;
  onClose: () => void;
  currentlyPlaying: SectionState<CurrentlyPlayingResponse>;
  recentlyPlayed: SectionState<RecentlyPlayedResponse>;
  topTracks: SectionState<TopTracksResponse>;
  topArtists: SectionState<TopArtistsResponse>;
  onRetryCurrentlyPlaying: () => void;
  onRetryRecentlyPlayed: () => void;
  onRetryTopTracks: () => void;
  onRetryTopArtists: () => void;
};

export function ListeningDrawer(props: ListeningDrawerProps) {
  return (
    <Drawer title="Listening" open={props.open} onClose={props.onClose}>
      <div className="listening-drawer">
        <DashboardSection
          title="Now playing"
          state={props.currentlyPlaying}
          onRetry={props.onRetryCurrentlyPlaying}
        >
          {(data) => <NowPlaying data={data} />}
        </DashboardSection>

        <DashboardSection
          title="Recently played"
          state={props.recentlyPlayed}
          onRetry={props.onRetryRecentlyPlayed}
        >
          {(data) => <RecentTrackList items={data.items} />}
        </DashboardSection>

        <DashboardSection
          title="Top tracks"
          state={props.topTracks}
          onRetry={props.onRetryTopTracks}
        >
          {(data) => <TopTrackList items={data.items} />}
        </DashboardSection>

        <DashboardSection
          title="Top artists"
          state={props.topArtists}
          onRetry={props.onRetryTopArtists}
        >
          {(data) => <ArtistList items={data.items} />}
        </DashboardSection>
      </div>
    </Drawer>
  );
}
