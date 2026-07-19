import type { CSSProperties } from "react";

/** Shared data-table styles (Stripe tnum discipline): uppercase-tracked muted
 *  headers on the cream band, hairline-soft row rules, right-aligned
 *  tabular-nums numeric cells. Spread into <table>/<th>/<td> style props. */
export const tableStyles: Record<string, CSSProperties> = {
  scroll: { overflowX: "auto", maxWidth: "100%" },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 13,
    color: "var(--body)",
  },
  th: {
    textAlign: "right",
    padding: "10px 14px",
    background: "var(--canvas)",
    color: "var(--muted)",
    fontWeight: 600,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    borderBottom: "var(--hairline)",
    whiteSpace: "nowrap",
  },
  thLeft: {
    textAlign: "left",
    padding: "10px 14px",
    background: "var(--canvas)",
    color: "var(--muted)",
    fontWeight: 600,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    borderBottom: "var(--hairline)",
  },
  td: {
    textAlign: "right",
    padding: "10px 14px",
    borderBottom: "var(--hairline-soft)",
    fontVariantNumeric: "tabular-nums",
  },
  tdLeft: { textAlign: "left", padding: "10px 14px", borderBottom: "var(--hairline-soft)" },
  rowWarn: { background: "rgba(198, 69, 69, 0.05)" },
};
