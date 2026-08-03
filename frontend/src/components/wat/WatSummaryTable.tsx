import { useState } from "react";
import type { WatItemStats } from "../../types";
import { STATUS_COLOR, STATUS_MARK } from "../../theme";
import WatItemTrendChart from "./WatItemTrendChart";
import { tableStyles } from "../../ui/tableStyles";
import { fmtCpk, fmtValue } from "../../ui/format";

interface Props {
  items: WatItemStats[];
}

export default function WatSummaryTable({ items }: Props) {
  const [openItem, setOpenItem] = useState<string | null>(null);

  return (
    <div style={styles.card}>
      <table style={tableStyles.table}>
        <thead>
          <tr>
            <th style={{ ...tableStyles.thLeft, ...styles.markCol }} />
            <th style={tableStyles.thLeft}>Item</th>
            <th style={tableStyles.thLeft}>Unit</th>
            <th style={tableStyles.th}>Low</th>
            <th style={tableStyles.th}>High</th>
            <th style={tableStyles.th}>N</th>
            <th style={tableStyles.th}>Mean</th>
            <th style={tableStyles.th}>σ</th>
            <th style={tableStyles.th}>Min</th>
            <th style={tableStyles.th}>Max</th>
            <th style={tableStyles.th}>Cpk</th>
            <th style={tableStyles.th}>OOS</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const open = openItem === item.item_name;
            return [
              <tr
                key={item.item_name}
                onClick={() => setOpenItem(open ? null : item.item_name)}
                style={{
                  ...styles.row,
                  ...(item.status === "red" ? styles.rowRed : {}),
                  ...(item.status === "yellow" ? styles.rowYellow : {}),
                  ...(open ? styles.rowOpen : {}),
                }}
              >
                <td style={{ ...tableStyles.tdLeft, color: STATUS_COLOR[item.status] }}>
                  {STATUS_MARK[item.status]}
                </td>
                <td style={tableStyles.tdLeft}>{item.item_name}</td>
                <td style={tableStyles.tdLeft}>{item.unit}</td>
                <td style={tableStyles.td}>{fmtValue(item.spec_low)}</td>
                <td style={tableStyles.td}>{fmtValue(item.spec_high)}</td>
                <td style={tableStyles.td}>{item.n}</td>
                <td style={tableStyles.td}>{fmtValue(item.mean)}</td>
                <td style={tableStyles.td}>{fmtValue(item.sigma)}</td>
                <td style={tableStyles.td}>{fmtValue(item.min)}</td>
                <td style={tableStyles.td}>{fmtValue(item.max)}</td>
                <td style={tableStyles.td}>{fmtCpk(item.cpk, item.cpk_state)}</td>
                <td
                  style={tableStyles.td}
                  title={item.oos_count > 0 ? `${item.oos_pct.toFixed(3)} % of measurements` : undefined}
                >
                  {item.oos_count}
                </td>
              </tr>,
              open ? (
                <tr key={`${item.item_name}-chart`}>
                  <td colSpan={12} style={styles.chartCell}>
                    <WatItemTrendChart item={item} />
                  </td>
                </tr>
              ) : null,
            ];
          })}
        </tbody>
      </table>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: 8,
    marginBottom: 20,
    overflowX: "auto",
  },
  markCol: { width: 24 },
  row: { cursor: "pointer" },
  rowRed: { background: "rgba(198, 69, 69, 0.06)" },
  rowYellow: { background: "rgba(212, 160, 23, 0.08)" },
  rowOpen: { background: "var(--surface-soft)" },
  chartCell: { padding: "8px 4px 16px" },
};
