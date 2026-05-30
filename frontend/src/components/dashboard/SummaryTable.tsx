import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { SummaryRow } from "../../types";
import Sparkline from "./Sparkline";

type SortKey = "display_name" | "process" | "latest_yield" | "avg_yield_6m" | "delta";

interface Props {
  rows: SummaryRow[];
}

export default function SummaryTable({ rows }: Props) {
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<SortKey>("delta");
  const [asc, setAsc] = useState(true);

  const sorted = [...rows].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av == null) return 1;
    if (bv == null) return -1;
    if (av < bv) return asc ? -1 : 1;
    if (av > bv) return asc ? 1 : -1;
    return 0;
  });

  const toggleSort = (k: SortKey) => {
    if (k === sortKey) setAsc(!asc);
    else { setSortKey(k); setAsc(true); }
  };

  const fmt = (n: number | null, suffix = "") =>
    n == null ? "—" : `${n.toFixed(1)}${suffix}`;

  return (
    <table style={styles.table}>
      <thead>
        <tr>
          <th style={styles.thLeft} onClick={() => toggleSort("display_name")}>製品 / Proc</th>
          <th style={styles.th} onClick={() => toggleSort("latest_yield")}>直近歩留</th>
          <th style={styles.th} onClick={() => toggleSort("avg_yield_6m")}>6m平均</th>
          <th style={styles.th} onClick={() => toggleSort("delta")}>差分</th>
          <th style={styles.th}>トレンド</th>
          <th style={styles.thLeft}>要注意</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => {
          const warn = r.warnings.length > 0;
          const deltaColor = r.delta == null ? "#888" : r.delta < 0 ? "#b13a2a" : "#2f8a3e";
          return (
            <tr
              key={`${r.nickname}-${r.process}`}
              style={{ ...styles.tr, ...(warn ? styles.trWarn : {}) }}
              onClick={() => navigate(`/explore/${encodeURIComponent(r.nickname)}/${r.process}`)}
            >
              <td style={styles.tdLeft}>
                <b>{r.display_name}</b> <span style={styles.proc}>/ {r.process}</span>
              </td>
              <td style={styles.td}>{fmt(r.latest_yield, "%")}</td>
              <td style={styles.td}>{fmt(r.avg_yield_6m, "%")}</td>
              <td style={{ ...styles.td, color: deltaColor }}>
                {r.delta == null ? "—" : `${r.delta < 0 ? "▼" : "▲"} ${Math.abs(r.delta).toFixed(1)}`}
              </td>
              <td style={styles.td}>
                <Sparkline
                  values={r.sparkline.map((p) => p.yield_pct)}
                  color={warn ? "#b13a2a" : "#3a7bbf"}
                />
              </td>
              <td style={styles.tdLeft}>
                {r.warnings.map((w, i) => (
                  <span key={i} style={styles.badge}>⚠ {w.message}</span>
                ))}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

const styles: Record<string, React.CSSProperties> = {
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: { textAlign: "right", padding: "8px 12px", background: "#f3efe4", cursor: "pointer", color: "#5a5547", fontWeight: 600, borderBottom: "1px solid #e6e1d4" },
  thLeft: { textAlign: "left", padding: "8px 12px", background: "#f3efe4", cursor: "pointer", color: "#5a5547", fontWeight: 600, borderBottom: "1px solid #e6e1d4" },
  tr: { cursor: "pointer", borderBottom: "1px solid #eee" },
  trWarn: { background: "#fff8e6" },
  td: { textAlign: "right", padding: "8px 12px" },
  tdLeft: { textAlign: "left", padding: "8px 12px" },
  proc: { color: "#888" },
  badge: { display: "inline-block", background: "#fff2d6", color: "#a06800", fontSize: 11, padding: "1px 6px", borderRadius: 10, marginRight: 4 },
};
