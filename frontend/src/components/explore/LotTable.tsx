import { Link } from "react-router-dom";
import type { LotData } from "../../types";
import { last8 } from "../../utils/tpRev";
import { tableStyles } from "../../ui/tableStyles";
import Badge from "../../ui/Badge";

interface Props {
  lots: LotData[];
  availableBins: string[];
  productId: string;
  process: string;
  sub?: string;
}

export default function LotTable({ lots, availableBins, productId, process, sub }: Props) {
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
                <Link
                  to={`/wafermap?product_id=${encodeURIComponent(productId)}&process=${process}&lots=${encodeURIComponent(lot.lot_id)}${sub ? `&sub=${encodeURIComponent(sub)}` : ""}`}
                  style={styles.lotLink}
                  title={`${lot.lot_id} のwafer mapを見る`}
                >
                  <span style={styles.cellTrunc}>{lot.lot_id}</span>
                </Link>
              </td>
              <td style={styles.tdLeft}>
                <span title={lot.test_program_rev} style={styles.cellTrunc}>{last8(lot.test_program_rev) || "—"}</span>
              </td>
              <td style={styles.tdLeft}>{lot.lot_date}</td>
              <td style={styles.tdLeft}>{lot.wafer_count}</td>
              <td style={styles.td}>{lot.yield_pct.toFixed(1)}%</td>
              {availableBins.map((b) => <td key={b} style={styles.td}>{pctFor(lot, b).toFixed(2)}%</td>)}
              <td style={styles.tdLeft}>
                {lot.warnings.map((w, i) => (
                  <span key={i} style={{ marginRight: 4 }}><Badge variant="error">⚠ {w.message}</Badge></span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  scroll: { ...tableStyles.scroll },
  table: { ...tableStyles.table, tableLayout: "fixed", fontSize: 12 },
  th: { ...tableStyles.th, padding: "8px 10px", letterSpacing: "0.03em" },
  thLeft: { ...tableStyles.thLeft, padding: "8px 10px", letterSpacing: "0.03em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  td: { ...tableStyles.td, padding: "6px 10px" },
  tdLeft: { ...tableStyles.tdLeft, padding: "6px 10px" },
  warn: { ...tableStyles.rowWarn },
  binHead: { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  cellTrunc: { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  lotLink: { display: "block", color: "var(--primary)", textDecoration: "none", fontWeight: 500 },
};
