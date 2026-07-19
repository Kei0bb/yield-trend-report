import type { CSSProperties, ReactNode } from "react";

export interface CheckListOption {
  value: string;
  label: string;
  swatch?: string;    // optional color dot (bin filter)
  disabled?: boolean; // e.g. lots beyond MAX_LOTS
}

interface CheckListCardProps {
  title: string;
  options: CheckListOption[];
  /** Checked values. Single-select callers pass `[value]` and replace it in onToggle. */
  selected: string[];
  onToggle: (value: string) => void;
  headerRight?: ReactNode;
  footer?: ReactNode;
  grow?: number;
  minWidth?: number;
  height?: number;
  /** Shown inside the scroll box when there are no options (loading / empty). */
  emptyText?: string;
}

/** Titled fixed-height card with a bordered scroll box of checkbox rows —
 *  the unified filter-card design from the wafer-map tab, now shared. */
export default function CheckListCard({
  title, options, selected, onToggle, headerRight, footer,
  grow = 1, minWidth = 0, height = 340, emptyText,
}: CheckListCardProps) {
  return (
    <div style={{ ...styles.card, flex: `${grow} 1 0`, minWidth, height }}>
      <div style={styles.header}>
        <span style={styles.title}>{title}</span>
        {headerRight && <div style={styles.headerRight}>{headerRight}</div>}
      </div>
      <div style={styles.list}>
        {options.length === 0 && emptyText && <p style={styles.empty}>{emptyText}</p>}
        {options.map((o) => (
          <label
            key={o.value}
            style={{ ...styles.item, ...(o.disabled ? styles.itemDisabled : {}) }}
          >
            <input
              type="checkbox"
              checked={selected.includes(o.value)}
              disabled={o.disabled}
              onChange={() => onToggle(o.value)}
            />
            {o.swatch && <span style={{ ...styles.swatch, background: o.swatch }} />}
            <span style={styles.itemText} title={o.label}>{o.label}</span>
          </label>
        ))}
      </div>
      {footer}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: 20,
    marginBottom: 0,
    display: "flex",
    flexDirection: "column",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  headerRight: { display: "flex", alignItems: "center", gap: 10 },
  title: { fontSize: 14, fontWeight: 600, color: "var(--ink)" },
  list: {
    flex: 1,
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    gap: 4,
    overflowY: "auto",
    border: "var(--hairline)",
    borderRadius: "var(--radius-control)",
    padding: 6,
  },
  item: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    fontWeight: 500,
    color: "var(--body)",
    padding: "4px 8px",
    borderRadius: 6,
    cursor: "pointer",
  },
  itemDisabled: { color: "var(--muted-soft)", cursor: "not-allowed" },
  itemText: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  swatch: { width: 10, height: 10, borderRadius: "50%", flexShrink: 0 },
  empty: { color: "var(--muted-soft)", fontSize: 13, padding: 4 },
};
