import { useEffect, type ReactNode } from "react";

type DrawerProps = {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  /** When true, backdrop lets pointer events through so drops hit the stage. */
  passThroughBackdrop?: boolean;
  /** Soft/clear dim so the stage stays visible as a drop target (Listening). */
  softBackdrop?: boolean;
};

export function Drawer({
  title,
  open,
  onClose,
  children,
  passThroughBackdrop = false,
  softBackdrop = false,
}: DrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className={
        [
          "drawer-root",
          softBackdrop ? "drawer-root--soft-backdrop" : "",
          passThroughBackdrop ? "drawer-root--pass-through" : "",
        ]
          .filter(Boolean)
          .join(" ")
      }
      role="presentation"
    >
      <button
        type="button"
        className="drawer-backdrop"
        aria-label="Close panel"
        onClick={onClose}
        tabIndex={passThroughBackdrop ? -1 : 0}
      />
      <aside
        className="drawer-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="drawer-header">
          <h2 className="drawer-title">{title}</h2>
          <button
            type="button"
            className="drawer-close"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}
