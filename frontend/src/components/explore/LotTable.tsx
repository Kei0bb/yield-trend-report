import type { LotData } from "../../types";

interface Props {
  lots: LotData[];
  availableBins: string[];
}

export default function LotTable({ lots, availableBins }: Props) {
  const pctFor = (lot: LotData, bin: string) => {
    const b = lot.bin_breakdown.find((x) => x.bin_name === bin);
    return b ? b.percent : 0;
  };
  const rows = [...lots].reverse();

  return (
    <table style={styles.table}>
      <thead>
        <tr>
          <th style={styles.thLeft}>Lot ID</th>
          <th style={styles.th}>Date</th>
          <th style={styles.th}>Wafers</th>
          <th style={styles.th}>Yield</th>
          {availableBins.map((b) => <th key={b} style={styles.th}>{b}</th>)}
          <th style={styles.thLeft}>⚠</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((lot) => (
          <tr key={lot.lot_id} style={lot.warnings.length ? styles.warn : undefined}>
            <td style={styles.tdLeft}>{lot.lot_id}</td>
            <td style={styles.td}>{lot.lot_date}</td>
            <td style={styles.td}>{lot.wafer_count}</td>
            <td style={styles.td}>{lot.yield_pct.toFixed(1)}%</td>
            {availableBins.map((b) => <td key={b} style={styles.td}>{pctFor(lot, b).toFixed(2)}%</td>)}
            <td style={styles.tdLeft}>
              {lot.warnings.map((w, i) => <span key={i} style={styles.badge}>⚠ {w.message}</span>)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const styles: Record<string, React.CSSProperties> = {
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12, color: "var(--gray-700)" },
  th: { textAlign: "right", padding: "8px 10px", background: "var(--warm-white)", borderBottom: "var(--border-whisper)", whiteSpace: "nowrap", color: "var(--gray-500)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.03em" },
  thLeft: { textAlign: "left", padding: "8px 10px", background: "var(--warm-white)", borderBottom: "var(--border-whisper)", color: "var(--gray-500)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.03em" },
  td: { textAlign: "right", padding: "6px 10px", borderBottom: "var(--border-soft)", fontVariantNumeric: "tabular-nums" },
  tdLeft: { textAlign: "left", padding: "6px 10px", borderBottom: "var(--border-soft)" },
  warn: { background: "rgba(224, 62, 62, 0.05)" },
  badge: { display: "inline-block", background: "rgba(224, 62, 62, 0.1)", color: "var(--red)", fontSize: 10, fontWeight: 500, padding: "2px 7px", borderRadius: 999, marginRight: 4 },
};
