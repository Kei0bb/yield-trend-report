import type { YieldRequest, YieldResponse } from "../types";
import YieldChart from "./YieldChart";
import { BIN_COLORS } from "../theme";

interface ReportViewProps {
  data: YieldResponse | null;
  request: YieldRequest | null;
}

export default function ReportView({ data, request }: ReportViewProps) {
  if (!data || !request) {
    return (
      <main style={styles.empty}>
        <div style={styles.emptyCard}>
          <div style={styles.emptyBadge}>Ready</div>
          <h2 style={styles.emptyTitle}>Generate your yield report</h2>
          <p style={styles.emptyText}>
            Pick a product, period, and test process on the left, then hit{" "}
            <b>Generate Report</b> to see lot-level yield trends and failure-bin
            breakdown per process.
          </p>
        </div>
      </main>
    );
  }

  const sortedProcesses = request.processes.filter((p) => p in data.data);

  // Shared bin-name -> color map across all processes, so the same bin name
  // gets the same color in every chart (first-appearance order across
  // sortedProcesses, then within each process's fail_bins keys).
  const binNameOrder: string[] = [];
  for (const process of sortedProcesses) {
    const processData = Object.values(data.data[process])[0];
    if (!processData) continue;
    for (const binName of Object.keys(processData.fail_bins)) {
      if (!binNameOrder.includes(binName)) binNameOrder.push(binName);
    }
  }
  const colorMap: Record<string, string> = {};
  binNameOrder.forEach((binName, i) => {
    colorMap[binName] = BIN_COLORS[i % BIN_COLORS.length];
  });

  // display_name = first key of the first process's data (the backend groups by
  // display_name, merging revision variants of the same product into one series).
  const firstProcess = sortedProcesses[0];
  const displayName = firstProcess ? Object.keys(data.data[firstProcess])[0] : undefined;

  const today = new Date().toISOString().slice(0, 10);
  const periodStart = (() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 3);
    return d.toISOString().slice(0, 10);
  })();
  // request.products holds the product_id (UI selection key). The title shows the
  // product_id as primary, with the product name (display_name) as secondary meta.
  const productId = request.products[0];
  const titleText = productId;
  const showDisplayName = displayName != null && displayName !== productId;

  return (
    <main style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>{titleText}</h1>
        <div style={styles.metaRow}>
          {showDisplayName && (
            <>
              <span style={styles.metaItem}>
                <span style={styles.metaLabel}>Name</span>
                {displayName}
              </span>
              <span style={styles.metaDivider} />
            </>
          )}
          <span style={styles.metaItem}>
            <span style={styles.metaLabel}>Period</span>
            {periodStart} → {today}
          </span>
          <span style={styles.metaDivider} />
          <span style={styles.metaItem}>
            <span style={styles.metaLabel}>Processes</span>
            {request.processes.join(" · ")}
          </span>
          <span style={styles.metaDivider} />
          <span style={styles.metaItem}>
            <span style={styles.metaLabel}>Generated</span>
            {today}
          </span>
        </div>
      </header>

      <div style={styles.grid}>
        {sortedProcesses.map((process) => {
          const processData = Object.values(data.data[process])[0];
          if (!processData) return null;
          return (
            <YieldChart key={process} processName={process} data={processData} colorMap={colorMap} />
          );
        })}
      </div>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    flex: 1,
    padding: "40px 56px 56px",
    overflowY: "auto",
    background: "var(--canvas)",
    minWidth: 0,
  },
  header: { marginBottom: 32 },
  title: {
    fontSize: 26,
    fontWeight: 700,
    color: "var(--ink)",
    letterSpacing: "-0.02em",
    lineHeight: 1.2,
    marginBottom: 12,
  },
  metaRow: {
    display: "flex",
    alignItems: "center",
    gap: 14,
    flexWrap: "wrap",
    fontSize: 13,
    color: "var(--muted)",
    fontVariantNumeric: "tabular-nums",
  },
  metaItem: { display: "inline-flex", alignItems: "center", gap: 6 },
  metaLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted-soft)",
  },
  metaDivider: { width: 1, height: 12, background: "var(--hairline-color)" },
  grid: { display: "flex", flexDirection: "column", gap: 24 },
  empty: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--canvas)",
    padding: 40,
  },
  emptyCard: {
    maxWidth: 460,
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: "36px 32px",
    textAlign: "center",
  },
  emptyBadge: {
    display: "inline-block",
    padding: "3px 10px",
    borderRadius: "var(--radius-pill)",
    background: "var(--surface-soft)",
    color: "var(--body)",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.04em",
    marginBottom: 14,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 600,
    color: "var(--ink)",
    letterSpacing: "-0.015em",
    marginBottom: 10,
  },
  emptyText: { fontSize: 14, lineHeight: 1.55, color: "var(--muted)" },
};
