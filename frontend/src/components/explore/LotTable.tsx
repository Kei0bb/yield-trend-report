import type { LotData } from "../../types";
import { last8 } from "../../utils/tpRev";

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

  // Left identity columns are fixed-width to their content (Lot ID 6ch,
  // Prog Rev 8ch, Date 10ch, Wafers 2ch), all left-aligned; the freed space
  // goes to wider bin and alert columns.
  const minWidth = 68 + 84 + 92 + 56 + 58 + availableBins.length * 76 + 220;

  return (
    <div style={styles.scroll}>
      <table style={{ ...styles.table, minWidth }}>
        <colgroup>
          <col style={{ width: 68 }} />
          <col style={{ width: 84 }} />
          <col style={{ width: 92 }} />
          <col style={{ width: 56 }} />
          <col style={{ width: 58 }} />
          {availableBins.map((b) => <col key={b} style={{ width: 76 }} />)}
          <col style={{ width: 220 }} />
        </colgroup>
        <thead>
          <tr>
            <th style={styles.thLeft}>Lot ID</th>
            <th style={styles.thLeft}>Prog Rev</th>
            <th style={styles.thLeft}>Date</th>
            <th style={styles.thLeft}>QTY</th>
            <th style={styles.th}>Yield</th>
            {availableBins.map((b) => (
              <th key={b} style={styles.th}>
                <span title={b} style={styles.binHead}>{b}</span>
              </th>
            ))}
            <th style={styles.thLeft}>⚠</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((lot) => (
            <tr key={`${lot.lot_id}|${lot.test_program_rev}`} style={lot.warnings.length ? styles.warn : undefined}>
              <td style={styles.tdLeft}>
                <span title={lot.lot_id} style={styles.cellTrunc}>{lot.lot_id}</span>
              </td>
              <td style={styles.tdLeft}>
                <span title={lot.test_program_rev} style={styles.cellTrunc}>{last8(lot.test_program_rev) || "—"}</span>
              </td>
              <td style={styles.tdLeft}>{lot.lot_date}</td>
              <td style={styles.tdLeft}>{lot.wafer_count}</td>
              <td style={styles.td}>{lot.yield_pct.toFixed(1)}%</td>
              {availableBins.map((b) => <td key={b} style={styles.td}>{pctFor(lot, b).toFixed(2)}%</td>)}
              <td style={styles.tdLeft}>
                {lot.warnings.map((w, i) => <span key={i} style={styles.badge}>⚠ {w.message}</span>)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  scroll: { overflowX: "auto", maxWidth: "100%" },
  table: { width: "100%", tableLayout: "fixed", borderCollapse: "collapse", fontSize: 12, color: "var(--gray-700)" },
  th: { textAlign: "right", padding: "8px 10px", background: "var(--warm-white)", borderBottom: "var(--border-whisper)", whiteSpace: "nowrap", color: "var(--gray-500)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.03em" },
  thLeft: { textAlign: "left", padding: "8px 10px", background: "var(--warm-white)", borderBottom: "var(--border-whisper)", color: "var(--gray-500)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.03em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  td: { textAlign: "right", padding: "6px 10px", borderBottom: "var(--border-soft)", fontVariantNumeric: "tabular-nums" },
  tdLeft: { textAlign: "left", padding: "6px 10px", borderBottom: "var(--border-soft)" },
  warn: { background: "rgba(224, 62, 62, 0.05)" },
  badge: { display: "inline-block", background: "rgba(224, 62, 62, 0.1)", color: "var(--red)", fontSize: 10, fontWeight: 500, padding: "2px 7px", borderRadius: 999, marginRight: 4 },
  binHead: { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  cellTrunc: { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
};
