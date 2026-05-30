import type { LotData } from "../../types";
import { formatLotId, type LotIdFormat } from "../../utils/formatLotId";

interface Props {
  lots: LotData[];
  availableBins: string[];
  format: LotIdFormat;
}

export default function LotTable({ lots, availableBins, format }: Props) {
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
          <th style={styles.th}>日付</th>
          <th style={styles.th}>Wafer数</th>
          <th style={styles.th}>歩留</th>
          {availableBins.map((b) => <th key={b} style={styles.th}>{b}</th>)}
          <th style={styles.thLeft}>⚠</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((lot) => (
          <tr key={lot.lot_id} style={lot.warnings.length ? styles.warn : undefined}>
            <td style={styles.tdLeft}>{formatLotId(lot.lot_id, lot.lot_date, format)}</td>
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
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12, marginTop: 20 },
  th: { textAlign: "right", padding: "6px 8px", background: "#f3efe4", borderBottom: "1px solid #e6e1d4", whiteSpace: "nowrap" },
  thLeft: { textAlign: "left", padding: "6px 8px", background: "#f3efe4", borderBottom: "1px solid #e6e1d4" },
  td: { textAlign: "right", padding: "5px 8px", borderBottom: "1px solid #eee" },
  tdLeft: { textAlign: "left", padding: "5px 8px", borderBottom: "1px solid #eee" },
  warn: { background: "#fff8e6" },
  badge: { display: "inline-block", background: "#fff2d6", color: "#a06800", fontSize: 10, padding: "1px 5px", borderRadius: 8, marginRight: 4 },
};
