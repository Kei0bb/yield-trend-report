import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Warning } from "../../types";
import Badge from "../../ui/Badge";

interface Props {
  warnings: Warning[];
}

const MARGIN = 8;
const POPOVER_WIDTH = 280;
// Grace period so the pointer can travel from the badge into the popover
// (e.g. to scroll a long list) without the hover-opened popover closing.
const HOVER_CLOSE_DELAY_MS = 150;

/** Compact "⚠ N" trigger for a row's warnings; expands into a popover
 *  listing every warning on hover, click, or keyboard focus. Portaled to
 *  document.body and positioned with `fixed` coordinates from the trigger's
 *  bounding rect so it escapes the table card's `overflow: hidden`. */
export default function WarningsPopover({ warnings }: Props) {
  const [open, setOpen] = useState(false);
  // Whether the current open came from hover — only hover-opened popovers
  // close on mouse leave; click/focus-opened ones stay until an explicit
  // dismissal (outside click, Escape, scroll).
  const [hoverOpen, setHoverOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const closeTimerRef = useRef<number | null>(null);

  const cancelScheduledClose = () => {
    if (closeTimerRef.current != null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };
  const openPopover = (viaHover: boolean) => {
    cancelScheduledClose();
    setOpen(true);
    setHoverOpen(viaHover);
  };
  const closePopover = () => {
    cancelScheduledClose();
    setOpen(false);
  };
  const scheduleHoverClose = () => {
    if (!hoverOpen) return;
    cancelScheduledClose();
    closeTimerRef.current = window.setTimeout(() => setOpen(false), HOVER_CLOSE_DELAY_MS);
  };

  useEffect(() => cancelScheduledClose, []);

  // Position (and reposition) the popover synchronously before paint so it
  // never flashes at the wrong spot. Flips above the trigger when there's
  // not enough room below, and clamps horizontally inside the viewport.
  useLayoutEffect(() => {
    if (!open) return;
    const reposition = () => {
      const btn = btnRef.current;
      const pop = popRef.current;
      if (!btn) return;
      const rect = btn.getBoundingClientRect();
      const popH = pop?.offsetHeight ?? 0;
      const popW = pop?.offsetWidth ?? POPOVER_WIDTH;
      const spaceBelow = window.innerHeight - rect.bottom;
      const flip = spaceBelow < popH + MARGIN && rect.top > popH + MARGIN;
      let left = rect.left;
      left = Math.min(left, window.innerWidth - popW - MARGIN);
      left = Math.max(MARGIN, left);
      const top = flip ? rect.top - popH - MARGIN : rect.bottom + MARGIN;
      setCoords({ top, left });
    };
    reposition();
    // Local close: the effect only depends on `open`; refs/setters are stable.
    const close = () => {
      if (closeTimerRef.current != null) window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
      setOpen(false);
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    const handleOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (btnRef.current?.contains(target)) return;
      if (popRef.current?.contains(target)) return;
      close();
    };
    // Closing on scroll (rather than repositioning) is acceptable and
    // avoids tracking every scrollable ancestor.
    const handleScroll = () => close();
    document.addEventListener("keydown", handleKey);
    document.addEventListener("mousedown", handleOutside);
    window.addEventListener("scroll", handleScroll, true);
    window.addEventListener("resize", reposition);
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.removeEventListener("mousedown", handleOutside);
      window.removeEventListener("scroll", handleScroll, true);
      window.removeEventListener("resize", reposition);
    };
  }, [open]);

  if (warnings.length === 0) return null;

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        style={styles.trigger}
        aria-label={`${warnings.length} warnings`}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          openPopover(false);
        }}
        onMouseEnter={() => {
          if (!open) openPopover(true);
        }}
        onMouseLeave={scheduleHoverClose}
        onFocus={() => {
          if (!open) openPopover(false);
        }}
        onBlur={closePopover}
      >
        <Badge variant="error">⚠ {warnings.length}</Badge>
      </button>
      {open &&
        createPortal(
          <div
            ref={popRef}
            role="dialog"
            aria-label={`${warnings.length} warnings`}
            onClick={(e) => e.stopPropagation()}
            // Keep focus on the trigger so clicking inside (e.g. the scrollbar)
            // doesn't blur it and close the popover.
            onMouseDown={(e) => e.preventDefault()}
            onMouseEnter={cancelScheduledClose}
            onMouseLeave={scheduleHoverClose}
            style={{
              ...styles.popover,
              top: coords?.top ?? -9999,
              left: coords?.left ?? -9999,
            }}
          >
            <div style={styles.header}>
              {warnings.length} warning{warnings.length === 1 ? "" : "s"}
            </div>
            <ul style={styles.list}>
              {warnings.map((w, i) => (
                <li key={`${w.type}-${w.bin_code}-${i}`} style={styles.item}>
                  <Badge variant="error">⚠ {w.message}</Badge>
                </li>
              ))}
            </ul>
          </div>,
          document.body
        )}
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  trigger: { background: "none", border: "none", padding: 0, cursor: "pointer", font: "inherit" },
  popover: {
    position: "fixed",
    width: POPOVER_WIDTH,
    maxHeight: 260,
    overflowY: "auto",
    background: "var(--surface-card)",
    borderRadius: "var(--radius-card)",
    boxShadow: "var(--shadow-popover)",
    padding: "10px 12px",
    zIndex: 1000,
  },
  header: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    color: "var(--muted-soft)",
    marginBottom: 8,
  },
  list: { display: "flex", flexDirection: "column", gap: 6, listStyle: "none" },
  item: {},
};
