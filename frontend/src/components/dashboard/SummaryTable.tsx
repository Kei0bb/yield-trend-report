import { Fragment, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { SummaryRow } from "../../types";
import Sparkline from "./Sparkline";

type SortKey = "product_id" | "process" | "latest_yield" | "avg_yield_6m" | "delta";

interface Props {
  rows: SummaryRow[];
}

const PROC_ORDER: Record<string, number> = { CP: 0, FT: 1, SLT: 2 };

/** Group rows into process-groups (each = a major row + its subs, OR an
 *  orphan subs-only group), then bucket those groups by product_id. Within a
 *  product, groups are ordered by a fixed process order (CP, then FT, then
 *  anything else). Products are ordered by the chosen sort key, read from
 *  each product's representative row (its CP group's first row if present,
 *  else its first group's first row). Respects `asc`. */
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

  // Bucket process-groups by product_id, preserving first-seen product order.
  const productOrder: string[] = [];
  const productGroups = new Map<string, SummaryRow[][]>();
  for (const group of groups) {
    const pid = group[0].product_id;
    if (!productGroups.has(pid)) {
      productGroups.set(pid, []);
      productOrder.push(pid);
    }
    productGroups.get(pid)!.push(group);
  }

  // Within each product, order process-groups by fixed CP -> FT -> other.
  for (const pid of productOrder) {
    const procGroups = productGroups.get(pid)!;
    procGroups.sort((ga, gb) => {
      const oa = PROC_ORDER[ga[0].process] ?? Number.MAX_SAFE_INTEGER;
      const ob = PROC_ORDER[gb[0].process] ?? Number.MAX_SAFE_INTEGER;
      return oa - ob;
    });
  }

  // Sort products by the chosen sort key, read from each product's
  // representative row: its CP group's first row if present, else its
  // first group's first row.
  productOrder.sort((pa, pb) => {
    const repFor = (pid: string): SummaryRow => {
      const procGroups = productGroups.get(pid)!;
      const cpGroup = procGroups.find((g) => g[0].process === "CP");
      return (cpGroup ?? procGroups[0])[0];
    };
    const av = repFor(pa)[sortKey];
    const bv = repFor(pb)[sortKey];
    if (av == null) return 1;
    if (bv == null) return -1;
    if (av < bv) return asc ? -1 : 1;
    if (av > bv) return asc ? 1 : -1;
    return 0;
  });

  // Flatten back to a single array: for each product (in sorted order), its
  // process-groups in fixed CP->FT order, each as [major(+subs)] or orphan subs.
  const result: SummaryRow[] = [];
  for (const pid of productOrder) {
    for (const group of productGroups.get(pid)!) {
      result.push(...group);
    }
  }
  return result;
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
          <th style={styles.th}>Target</th>
          <th style={styles.th} onClick={() => toggleSort("delta")}>Delta</th>
          <th style={styles.th}>Trend</th>
          <th style={styles.thLeft}>Alerts</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => {
          const warn = r.warnings.length > 0;
          const deltaColor = r.delta == null ? "var(--gray-400)" : r.delta < 0 ? "var(--red)" : "var(--green)";
          const belowTarget = r.latest_yield != null && r.target != null && r.latest_yield < r.target;
          const isSub = r.level === 1;
          const orphanKey = `${r.product_id}|${r.process}|${r.process_label}`;
          const isOrphanLead = isSub && orphanLeads.has(orphanKey);
          return (
            <Fragment key={`${r.nickname}-${r.process}-${r.level}-${r.process_label}`}>
              {/* subs-only product: show a filled, non-clickable major header
                  so the sub rows don't appear to dangle under nothing. */}
              {isOrphanLead && (
                <tr style={{ ...styles.tr, ...styles.trDisabled }}>
                  <td style={styles.tdLeft}>
                    <b>{r.product_id}</b> <span style={styles.proc}>/ {r.process}</span>
                    {r.display_name && r.display_name !== r.product_id && (
                      <div style={styles.subName}>{r.display_name}</div>
                    )}
                  </td>
                  <td style={styles.td}>—</td>
                  <td style={styles.td}>—</td>
                  <td style={styles.td}>—</td>
                  <td style={styles.td}>—</td>
                  <td style={styles.td} />
                  <td style={styles.tdLeft} />
                </tr>
              )}
            <tr
              style={{ ...styles.tr, ...(warn ? styles.trWarn : {}), ...(isSub ? styles.trSub : {}) }}
              onClick={() => navigate(
                `/explore/${encodeURIComponent(r.product_id)}/${r.process}` +
                (isSub ? `?sub=${encodeURIComponent(r.process_label)}` : "")
              )}
            >
              <td style={{ ...styles.tdLeft, ...(isSub ? styles.tdLeftSub : {}) }}>
                {isSub ? (
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
              <td style={{ ...styles.td, ...(belowTarget ? { color: "var(--red)" } : {}) }}>
                {fmt(r.latest_yield, "%")}
              </td>
              <td style={styles.td}>{fmt(r.avg_yield_6m, "%")}</td>
              <td style={styles.td}>{fmt(r.target ?? null, "%")}</td>
              <td style={{ ...styles.td, color: deltaColor }}>
                {r.delta == null ? "—" : `${r.delta < 0 ? "▼" : "▲"} ${Math.abs(r.delta).toFixed(1)}`}
              </td>
              <td style={styles.td}>
                <Sparkline
                  values={r.sparkline.map((p) => p.yield_pct)}
                  color={warn ? "#e03e3e" : "#0075de"}
                  target={r.target}
                />
              </td>
              <td style={styles.tdLeft}>
                {r.warnings.map((w, i) => (
                  <span key={i} style={styles.badge}>⚠ {w.message}</span>
                ))}
              </td>
            </tr>
            </Fragment>
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
  trDisabled: { cursor: "default", background: "var(--warm-white)", color: "var(--gray-500)" },
  td: { textAlign: "right", padding: "10px 14px", fontVariantNumeric: "tabular-nums" },
  tdLeft: { textAlign: "left", padding: "10px 14px" },
  tdLeftSub: { paddingLeft: 28 },
  proc: { color: "var(--gray-400)" },
  subGlyph: { color: "var(--gray-400)", marginRight: 6, userSelect: "none" },
  subName: { color: "var(--gray-400)", fontSize: 11, marginTop: 2 },
  badge: { display: "inline-block", background: "rgba(224, 62, 62, 0.1)", color: "var(--red)", fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 999, marginRight: 4 },
};
