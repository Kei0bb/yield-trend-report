import { useState } from "react";
import type { WatItemStats, WatSection } from "../../types";
import { STATUS_COLOR, STATUS_MARK } from "../../theme";
import { tableStyles } from "../../ui/tableStyles";
import { fmtCpk, fmtValue } from "../../ui/format";

/** The scalar columns this table draws. Both the single-lot and the trend
 *  item types satisfy it; neither series field is read here. */
export type WatTableRow = Omit<WatItemStats, "wafer_series">;

interface Props<T extends WatTableRow> {
  items: T[];
  /** Rendered inside the expanded row, under the clicked item. */
  renderChart: (item: T) => React.ReactNode;
}

/** Consecutive runs of one section. The backend already sorts items by
 *  section, so grouping only splits the list — it never reorders it. */
function groupBySection<T extends WatTableRow>(items: T[]): [WatSection, T[]][] {
  const groups: [WatSection, T[]][] = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last[0] === item.section) last[1].push(item);
    else groups.push([item.section, [item]]);
  }
  return groups;
}

export default function WatSummaryTable<T extends WatTableRow>(
  { items, renderChart }: Props<T>
) {
  const [openItem, setOpenItem] = useState<string | null>(null);

  const sectionRow = (section: WatSection, group: T[]) => {
    const reds = group.filter((i) => i.status === "red").length;
    const yellows = group.filter((i) => i.status === "yellow").length;
    return (
      <tr key={`section-${section}`}>
        <td colSpan={12} style={styles.sectionCell}>
          <span style={styles.sectionName}>{section}</span>
          <span style={styles.sectionMeta}>
            {group.length} item{group.length !== 1 ? "s" : ""}
          </span>
          {section === "Others" ? (
            <span style={styles.sectionMeta}>σ / Cpk / OOS not evaluated</span>
          ) : (
            <>
              {reds > 0 && (
                <span style={{ ...styles.sectionCount, color: STATUS_COLOR.red }}>
                  {STATUS_MARK.red} {reds}
                </span>
              )}
              {yellows > 0 && (
                <span style={{ ...styles.sectionCount, color: STATUS_COLOR.yellow }}>
                  {STATUS_MARK.yellow} {yellows}
                </span>
              )}
            </>
          )}
        </td>
      </tr>
    );
  };

  const itemRows = (item: T) => {
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
          {item.section === "Others" ? "—" : item.oos_count}
        </td>
      </tr>,
      open ? (
        <tr key={`${item.item_name}-chart`}>
          <td colSpan={12} style={styles.chartCell}>
            {renderChart(item)}
          </td>
        </tr>
      ) : null,
    ];
  };

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
          {groupBySection(items).flatMap(([section, group]) => [
            sectionRow(section, group),
            ...group.flatMap(itemRows),
          ])}
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
  sectionCell: {
    padding: "16px 14px 6px",
    borderBottom: "var(--hairline)",
  },
  sectionName: { fontSize: 13, fontWeight: 600, color: "var(--ink)", marginRight: 14 },
  sectionMeta: { fontSize: 12, color: "var(--muted-soft)", marginRight: 14 },
  sectionCount: { fontSize: 12, fontWeight: 600, marginRight: 14 },
};
