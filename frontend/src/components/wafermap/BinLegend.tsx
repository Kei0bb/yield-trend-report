import type { WaferMapLegendItem } from "../../types";

interface BinLegendProps {
  legend: WaferMapLegendItem[];
  colorFor: (bin: number) => string;
  selectedBins: number[];
  onToggle: (bin: number) => void;
}

export default function BinLegend({ legend, colorFor, selectedBins, onToggle }: BinLegendProps) {
  if (legend.length === 0) return null;

  return (
    <div style={styles.wrap}>
      {legend.map((item) => {
        const checked = selectedBins.includes(item.bin_code);
        return (
          <label key={item.bin_code} style={styles.item}>
            <input
              type="checkbox"
              checked={checked}
              onChange={() => onToggle(item.bin_code)}
            />
            <span style={{ ...styles.swatch, background: colorFor(item.bin_code) }} />
            <span>{item.label} ({item.count})</span>
          </label>
        );
      })}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { display: "flex", flexDirection: "column", gap: 6 },
  item: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    color: "var(--gray-700)",
    fontSize: 12,
    fontWeight: 500,
    cursor: "pointer",
  },
  swatch: { width: 10, height: 10, borderRadius: "50%", flexShrink: 0 },
};
