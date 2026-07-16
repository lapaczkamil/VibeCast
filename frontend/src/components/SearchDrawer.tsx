import { Drawer } from "./Drawer";
import { MoviesSearch } from "./MoviesSearch";

type SearchDrawerProps = {
  open: boolean;
  onClose: () => void;
};

export function SearchDrawer({ open, onClose }: SearchDrawerProps) {
  return (
    <Drawer title="Search movies" open={open} onClose={onClose}>
      <MoviesSearch />
    </Drawer>
  );
}
