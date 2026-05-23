import type { YieldRequest, YieldResponse } from "../types";
import YieldChart from "./YieldChart";

interface ReportViewProps {
  data: YieldResponse | null;
  request: YieldRequest | null;
}

const PROCESS_ORDER = ["CP", "FT", "SLT"];

export default function ReportView({ data, request }: ReportViewProps) {
  if (!data || !request) {
    return (
      <main style={styles.empty}>
        <div style={styles.emptyCard}>
          <div style={styles.emptyBadge}>Ready</div>
          <h2 style={styles.emptyTitle}>Generate your yield report</h2>
          <p style={styles.emptyText}>
            Pick a product (or multiple to compare), period, and test process on
            the left, then hit <b>Generate Report</b> to see lot-level yield
            trends and failure-bin breakdown per process.
          </p>
        </div>
      </main>
    );
  }

  const sortedProcesses = Object.keys(data.data).sort(
    (a, b) => PROCESS_ORDER.indexOf(a) - PROCESS_ORDER.indexOf(b)
  );

  // display_name 一覧 = data.data の最初の process の keys (バックエンドで
  // display_name でグループ化済み。改版品種は1つにマージされている)
  const firstProcess = sortedProcesses[0];
  const displayNames = firstProcess ? Object.keys(data.data[firstProcess]) : [];

  const today = new Date().toISOString().slice(0, 10);
  const periodStart = (() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 3);
    return d.toISOString().slice(0, 10);
  })();
  const isMultiDisplay = displayNames.length > 1;
  const titleText =
    displayNames.length > 0
      ? displayNames.join(" vs ")
      : request.products.join(" vs ");

  // 選択した nicknames と display_name が異なる場合 (= 改版マージ発生時) は明示
  const showSelectedNicknames =
    request.products.length !== displayNames.length ||
    request.products.some((p, i) => p !== displayNames[i]);

  return (
    <main style={styles.container}>
      <header style={styles.header}>
        <div style={styles.breadcrumb}>Reports · Yield Trend</div>
        <h1 style={styles.title}>{titleText}</h1>
        <div style={styles.metaRow}>
          {isMultiDisplay && (
            <>
              <span style={styles.metaItem}>
                <span style={styles.metaLabel}>Products</span>
                {displayNames.join(" · ")}
              </span>
              <span style={styles.metaDivider} />
            </>
          )}
          {showSelectedNicknames && (
            <>
              <span style={styles.metaItem}>
                <span style={styles.metaLabel}>Selected</span>
                {request.products.join(" · ")}
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
        {sortedProcesses.map((process) => (
          <YieldChart
            key={process}
            processName={process}
            productData={data.data[process]}
          />
        ))}
      </div>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    flex: 1,
    padding: "40px 56px 56px",
    overflowY: "auto",
    background: "var(--warm-white)",
    minWidth: 0,
  },
  header: {
    marginBottom: 32,
  },
  breadcrumb: {
    fontSize: 12,
    color: "var(--gray-400)",
    fontWeight: 500,
    letterSpacing: "0.02em",
    marginBottom: 8,
  },
  title: {
    fontSize: 32,
    fontWeight: 700,
    color: "var(--gray-700)",
    letterSpacing: "-0.025em",
    lineHeight: 1.15,
    marginBottom: 12,
  },
  metaRow: {
    display: "flex",
    alignItems: "center",
    gap: 14,
    flexWrap: "wrap",
    fontSize: 13,
    color: "var(--gray-500)",
  },
  metaItem: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
  },
  metaLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--gray-400)",
  },
  metaDivider: {
    width: 1,
    height: 12,
    background: "var(--gray-200)",
  },
  grid: {
    display: "flex",
    flexDirection: "column",
    gap: 24,
  },
  empty: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--warm-white)",
    padding: 40,
  },
  emptyCard: {
    maxWidth: 460,
    background: "var(--white)",
    border: "var(--border-whisper)",
    borderRadius: 12,
    padding: "36px 32px",
    boxShadow: "var(--shadow-card)",
    textAlign: "center",
  },
  emptyBadge: {
    display: "inline-block",
    padding: "3px 10px",
    borderRadius: 999,
    background: "var(--badge-bg)",
    color: "var(--badge-text)",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.04em",
    marginBottom: 14,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 600,
    color: "var(--gray-700)",
    letterSpacing: "-0.015em",
    marginBottom: 10,
  },
  emptyText: {
    fontSize: 14,
    lineHeight: 1.55,
    color: "var(--gray-500)",
  },
};
