import { useEffect, useState, useCallback } from "react";
import { fetchDashboardSummary } from "../api/client";
import type { DashboardSummaryResponse } from "../types";
import SummaryTable from "../components/dashboard/SummaryTable";

export default function DashboardPage() {
  const [months, setMonths] = useState(3);
  const [process, setProcess] = useState("all");
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchDashboardSummary(months, process, force));
    } catch (e) {
      console.error(e);
      setError("Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, [months, process]);

  useEffect(() => { load(false); }, [load]);

  return (
    <main style={styles.container}>
      <header style={styles.header}>
        <div style={styles.breadcrumb}>Monitoring · Yield Overview</div>
        <h1 style={styles.title}>Dashboard</h1>
      </header>

      <div style={styles.toolbar}>
        <label style={styles.field}>
          <span style={styles.fieldLabel}>Period</span>
          <select value={months} onChange={(e) => setMonths(Number(e.target.value))} style={styles.select}>
            <option value={1}>Last 1 month</option>
            <option value={3}>Last 3 months</option>
            <option value={6}>Last 6 months</option>
          </select>
        </label>
        <label style={styles.field}>
          <span style={styles.fieldLabel}>Process</span>
          <select value={process} onChange={(e) => setProcess(e.target.value)} style={styles.select}>
            <option value="all">All</option>
            <option value="CP">CP</option>
            <option value="FT">FT</option>
          </select>
        </label>
        <button onClick={() => load(true)} disabled={loading} style={styles.refresh}>
          {loading ? "Refreshing…" : "🔄 Refresh"}
        </button>
        {data && <span style={styles.updated}>Updated: {new Date(data.generated_at).toLocaleString()}</span>}
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {data && (
        <div style={styles.card}>
          <SummaryTable rows={data.rows} months={data.period.months} />
        </div>
      )}
      {data && data.rows.length === 0 && !loading && <p style={styles.empty}>No data available.</p>}
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
  header: { marginBottom: 24 },
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
  },
  toolbar: { display: "flex", alignItems: "center", gap: 18, marginBottom: 20, flexWrap: "wrap" },
  field: { display: "inline-flex", alignItems: "center", gap: 8 },
  fieldLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--gray-400)",
  },
  select: {
    padding: "6px 10px",
    borderRadius: 8,
    border: "var(--border-whisper)",
    background: "var(--white)",
    color: "var(--gray-700)",
    fontSize: 13,
    fontFamily: "var(--font-sans)",
  },
  refresh: {
    padding: "7px 16px",
    cursor: "pointer",
    borderRadius: 8,
    border: "var(--border-whisper)",
    background: "var(--white)",
    color: "var(--gray-700)",
    fontSize: 13,
    fontWeight: 500,
    boxShadow: "var(--shadow-button)",
  },
  updated: { fontSize: 12, color: "var(--gray-400)", marginLeft: "auto", fontVariantNumeric: "tabular-nums" },
  error: {
    background: "rgba(224, 62, 62, 0.08)",
    color: "var(--red)",
    padding: "10px 14px",
    borderRadius: 8,
    marginBottom: 16,
    fontSize: 13,
  },
  card: {
    background: "var(--white)",
    border: "var(--border-whisper)",
    borderRadius: 12,
    boxShadow: "var(--shadow-card)",
    overflow: "hidden",
  },
  empty: { color: "var(--gray-400)", fontSize: 14 },
};
