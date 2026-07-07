import type { WaferMapLegendItem } from "../../types";

interface BinLegendProps {
  legend: WaferMapLegendItem[];
  colorFor: (bin: number) => string;
  selectedBin: number | null;
  onSelect: (bin: number | null) => void;
}

export default function BinLegend({ legend, colorFor, selectedBin, onSelect }: BinLegendProps) {
  if (legend.length === 0) return null;

  return (
    <div style={styles.wrap}>
      {legend.map((item) => {
        const active = selectedBin === item.bin_code;
        return (
          <button
            key={item.bin_code}
            type="button"
            onClick={() => onSelect(active ? null : item.bin_code)}
            style={{ ...styles.chip, ...(active ? styles.chipActive : {}) }}
          >
            <span style={{ ...styles.swatch, background: colorFor(item.bin_code) }} />
            {item.label} ({item.count})
          </button>
        );
      })}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { display: "flex", flexWrap: "wrap", gap: 8 },
  chip: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    background: "var(--warm-white)",
    color: "var(--gray-700)",
    fontSize: 12,
    fontWeight: 500,
    padding: "4px 10px",
    borderRadius: 999,
    border: "1px solid transparent",
    cursor: "pointer",
  },
  chipActive: {
    border: "1px solid var(--notion-blue)",
    background: "rgba(35, 131, 226, 0.08)",
  },
  swatch: { width: 10, height: 10, borderRadius: "50%", flexShrink: 0 },
};
