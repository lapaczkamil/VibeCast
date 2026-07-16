type ComingSoonButtonProps = {
  label: string;
};

export function ComingSoonButton({ label }: ComingSoonButtonProps) {
  return (
    <button
      type="button"
      className="chrome-btn chrome-btn--soon"
      disabled
      aria-disabled="true"
      title="Coming soon"
    >
      <span>{label}</span>
      <span className="soon-badge" aria-hidden="true">
        Soon
      </span>
    </button>
  );
}
