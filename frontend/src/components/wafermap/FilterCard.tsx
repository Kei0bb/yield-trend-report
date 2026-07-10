import type { ReactNode } from "react";

export interface FilterOption { value: string; label: string; }

interface FilterCardProps {
  title: string;
  options: FilterOption[];
  value: string;
  onChange: (value: string) => void;
  grow?: number;
  minWidth?: number;
  footer?: ReactNode;
}

/** Titled fixed-height card with a bordered scroll box of single-select
 *  checkbox rows — visually matching the Lots / Bin-filter cards. Exactly
 *  one option is checked; clicking a row selects it. Width is flexible: the
 *  card grows to fill the row (weighted by `grow`) so the filter row spans
 *  the same full width as the wafer-map card below. */
export default function FilterCard({ title, options, value, onChange, grow = 1, minWidth = 0, footer }: FilterCardProps) {
  return (
    <div style={{ ...styles.card, flex: `${grow} 1 0`, minWidth }}>
      <div style={styles.header}><span style={styles.title}>{title}</span></div>
      <div style={styles.list}>
        {options.map((o) => (
          <label key={o.value} style={styles.item}>
            <input type="checkbox" checked={value === o.value} onChange={() => onChange(o.value)} />
            <span style={styles.itemText} title={o.label}>{o.label}</span>
          </label>
        ))}
      </div>
      {footer}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "var(--white)",
    border: "var(--border-whisper)",
    borderRadius: 12,
    boxShadow: "var(--shadow-card)",
    padding: 20,
    marginBottom: 0,
    height: 340,
    display: "flex",
    flexDirection: "column",
  },
  header: { display: "flex", alignItems: "center", marginBottom: 12 },
  title: { fontSize: 14, fontWeight: 600, color: "var(--gray-700)" },
  list: {
    flex: 1,
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    gap: 4,
    overflowY: "auto",
    border: "var(--border-whisper)",
    borderRadius: 8,
    padding: 6,
  },
  item: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    fontWeight: 500,
    color: "var(--gray-700)",
    padding: "4px 8px",
    borderRadius: 6,
    cursor: "pointer",
  },
  itemText: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
};
