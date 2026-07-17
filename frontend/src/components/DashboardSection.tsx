import type { ReactNode } from "react";
import type { SectionState } from "../types";

type DashboardSectionProps<T> = {
  title: string;
  state: SectionState<T>;
  onRetry: () => void;
  children: (data: T) => ReactNode;
};

export function DashboardSection<T>({
  title,
  state,
  onRetry,
  children,
}: DashboardSectionProps<T>) {
  return (
    <section className="dashboard-section">
      <h2 className="section-title">{title}</h2>
      {state.status === "idle" && (
        <p className="status-message section-status">Not loaded yet.</p>
      )}
      {state.status === "loading" && (
        <p className="status-message section-status">Loading…</p>
      )}
      {state.status === "error" && (
        <div className="section-error">
          <p className="status-message status-message--error">
            {state.error ?? "Something went wrong."}
          </p>
          <button type="button" className="cta cta--ghost" onClick={onRetry}>
            Try again
          </button>
        </div>
      )}
      {state.status === "ok" && state.data !== undefined && children(state.data)}
    </section>
  );
}
