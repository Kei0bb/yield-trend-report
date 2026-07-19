import { useEffect, useState, useCallback } from "react";
import { fetchDashboardSummary } from "../api/client";
import type { DashboardSummaryResponse } from "../types";
import SummaryTable from "../components/dashboard/SummaryTable";
import PageTitle from "../ui/PageTitle";
import Select from "../ui/Select";
import Button from "../ui/Button";

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
      <PageTitle breadcrumb="Monitoring · Yield Overview" title="Dashboard" />

      <div style={styles.toolbar}>
        <label style={styles.field}>
          <span style={styles.fieldLabel}>Period</span>
          <Select value={months} onChange={(e) => setMonths(Number(e.target.value))}>
            <option value={1}>Last 1 month</option>
            <option value={3}>Last 3 months</option>
            <option value={6}>Last 6 months</option>
          </Select>
        </label>
        <label style={styles.field}>
          <span style={styles.fieldLabel}>Process</span>
          <Select value={process} onChange={(e) => setProcess(e.target.value)}>
            <option value="all">All</option>
            <option value="CP">CP</option>
            <option value="FT">FT</option>
          </Select>
        </label>
        <Button onClick={() => load(true)} disabled={loading}>
          {loading ? "Refreshing…" : "🔄 Refresh"}
        </Button>
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
    background: "var(--canvas)",
    minWidth: 0,
  },
  toolbar: { display: "flex", alignItems: "center", gap: 18, marginBottom: 20, flexWrap: "wrap" },
  field: { display: "inline-flex", alignItems: "center", gap: 8 },
  fieldLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted-soft)",
  },
  updated: { fontSize: 12, color: "var(--muted-soft)", marginLeft: "auto", fontVariantNumeric: "tabular-nums" },
  error: {
    background: "rgba(198, 69, 69, 0.08)",
    color: "var(--error)",
    padding: "10px 14px",
    borderRadius: "var(--radius-control)",
    marginBottom: 16,
    fontSize: 13,
  },
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    overflow: "hidden",
  },
  empty: { color: "var(--muted-soft)", fontSize: 14 },
};
