import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { SummaryRow } from "../../types";
import Sparkline from "./Sparkline";

type SortKey = "product_id" | "process" | "latest_yield" | "avg_yield_6m" | "delta";

interface Props {
  rows: SummaryRow[];
}

/** Sort only the major (level 0) rows, then re-attach each major's sub rows
 *  (level 1) immediately after it. This preserves the major+sub grouping
 *  regardless of the chosen sort key.
 *
 *  A group may start with a level-1 row when the product uses subs-only config
 *  (no major row). Such an "orphan-lead" group is sorted by its first row. */
function sortGrouped(rows: SummaryRow[], sortKey: SortKey, asc: boolean): SummaryRow[] {
  // Build groups: each group = [major-or-first-sub, ...remaining-subs]
  const groups: SummaryRow[][] = [];
  for (const row of rows) {
    if (row.level === 0) {
      groups.push([row]);
    } else {
      // Attach sub to the most recent group that belongs to the same
      // product+process (handles subs-only groups correctly).
      const last = groups[groups.length - 1];
      if (
        groups.length > 0 &&
        last[0].product_id === row.product_id &&
        last[0].process === row.process
      ) {
        last.push(row);
      } else {
        // Orphan sub row (subs-only config) — start a new group
        groups.push([row]);
      }
    }
  }

  // Sort groups by the first row's sort key
  groups.sort((ga, gb) => {
    const av = ga[0][sortKey];
    const bv = gb[0][sortKey];
    if (av == null) return 1;
    if (bv == null) return -1;
    if (av < bv) return asc ? -1 : 1;
    if (av > bv) return asc ? 1 : -1;
    return 0;
  });

  // Flatten back to a single array
  return groups.flat();
}

export default function SummaryTable({ rows }: Props) {
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<SortKey>("delta");
  const [asc, setAsc] = useState(true);

  const sorted = sortGrouped(rows, sortKey, asc);

  // Pre-compute which level-1 rows are "orphan leads" (first in their
  // product+process group with no preceding level-0 major row).
  const orphanLeads = new Set<string>();
  {
    // Track the last-seen level-0 key per product+process
    const seenMajor = new Set<string>();
    for (const r of sorted) {
      const groupKey = `${r.product_id}|${r.process}`;
      if (r.level === 0) {
        seenMajor.add(groupKey);
      } else if (!seenMajor.has(groupKey)) {
        // First encounter of this product+process at level 1 with no major → orphan lead
        orphanLeads.add(`${groupKey}|${r.process_label}`);
        seenMajor.add(groupKey); // mark as seen so only the FIRST sub is orphan-lead
      }
    }
  }

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
          <th style={styles.thLeft} onClick={() => toggleSort("product_id")}>Product ID / Proc</th>
          <th style={styles.th} onClick={() => toggleSort("latest_yield")}>Latest</th>
          <th style={styles.th} onClick={() => toggleSort("avg_yield_6m")}>Avg</th>
          <th style={styles.th} onClick={() => toggleSort("delta")}>Delta</th>
          <th style={styles.th}>Trend</th>
          <th style={styles.thLeft}>Alerts</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => {
          const warn = r.warnings.length > 0;
          const deltaColor = r.delta == null ? "var(--gray-400)" : r.delta < 0 ? "var(--red)" : "var(--green)";
          const isSub = r.level === 1;
          const orphanKey = `${r.product_id}|${r.process}|${r.process_label}`;
          const isOrphanLead = isSub && orphanLeads.has(orphanKey);
          return (
            <tr
              key={`${r.nickname}-${r.process}-${r.level}-${r.process_label}`}
              style={{ ...styles.tr, ...(warn ? styles.trWarn : {}), ...(isSub && !isOrphanLead ? styles.trSub : {}) }}
              onClick={() => navigate(
                `/explore/${encodeURIComponent(r.product_id)}/${r.process}` +
                (isSub ? `?sub=${encodeURIComponent(r.process_label)}` : "")
              )}
            >
              <td style={{ ...styles.tdLeft, ...(isSub && !isOrphanLead ? styles.tdLeftSub : {}) }}>
                {isSub && !isOrphanLead ? (
                  <>
                    <span style={styles.subGlyph}>└</span>
                    <span style={styles.proc}>{r.process_label}</span>
                  </>
                ) : (
                  <>
                    <b>{r.product_id}</b> <span style={styles.proc}>/ {r.process_label}</span>
                    {r.display_name && r.display_name !== r.product_id && (
                      <div style={styles.subName}>{r.display_name}</div>
                    )}
                  </>
                )}
              </td>
              <td style={styles.td}>{fmt(r.latest_yield, "%")}</td>
              <td style={styles.td}>{fmt(r.avg_yield_6m, "%")}</td>
              <td style={{ ...styles.td, color: deltaColor }}>
                {r.delta == null ? "—" : `${r.delta < 0 ? "▼" : "▲"} ${Math.abs(r.delta).toFixed(1)}`}
              </td>
              <td style={styles.td}>
                <Sparkline
                  values={r.sparkline.map((p) => p.yield_pct)}
                  color={warn ? "#e03e3e" : "#0075de"}
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
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13, color: "var(--gray-700)" },
  th: { textAlign: "right", padding: "10px 14px", background: "var(--warm-white)", cursor: "pointer", color: "var(--gray-500)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em", borderBottom: "var(--border-whisper)" },
  thLeft: { textAlign: "left", padding: "10px 14px", background: "var(--warm-white)", cursor: "pointer", color: "var(--gray-500)", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em", borderBottom: "var(--border-whisper)" },
  tr: { cursor: "pointer", borderBottom: "var(--border-soft)" },
  trWarn: { background: "rgba(224, 62, 62, 0.05)" },
  trSub: { opacity: 0.85 },
  td: { textAlign: "right", padding: "10px 14px", fontVariantNumeric: "tabular-nums" },
  tdLeft: { textAlign: "left", padding: "10px 14px" },
  tdLeftSub: { paddingLeft: 28 },
  proc: { color: "var(--gray-400)" },
  subGlyph: { color: "var(--gray-400)", marginRight: 6, userSelect: "none" },
  subName: { color: "var(--gray-400)", fontSize: 11, marginTop: 2 },
  badge: { display: "inline-block", background: "rgba(224, 62, 62, 0.1)", color: "var(--red)", fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 999, marginRight: 4 },
};
