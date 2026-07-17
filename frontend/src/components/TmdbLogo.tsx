type TmdbLogoProps = {
  className?: string;
};

/** Official TMDB attribution mark — required when showing TMDB data. */
export function TmdbLogo({ className = "tmdb-logo" }: TmdbLogoProps) {
  return (
    <img
      className={className}
      src="/tmdb-logo.svg"
      alt="The Movie Database"
      width={46}
      height={20}
      loading="lazy"
      decoding="async"
    />
  );
}
