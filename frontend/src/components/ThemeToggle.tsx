import type { Theme } from "../lib/theme";

type ThemeToggleProps = {
  theme: Theme;
  onToggle: () => void;
};

export function ThemeToggle({ theme, onToggle }: ThemeToggleProps) {
  const nextLabel = theme === "light" ? "Switch to dark mode" : "Switch to light mode";
  return (
    <button
      type="button"
      className="chrome-btn theme-toggle"
      onClick={onToggle}
      aria-label={nextLabel}
      title={nextLabel}
    >
      {theme === "light" ? "Dark" : "Light"}
    </button>
  );
}
