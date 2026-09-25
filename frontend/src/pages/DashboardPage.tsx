import { useEffect, useState, useCallback, useRef } from "react";
import { fetchDashboardSummary } from "../api/client";
import type { DashboardSummaryResponse } from "../types";
import SummaryTable from "../components/dashboard/SummaryTable";
import PageTitle from "../ui/PageTitle";
import Select from "../ui/Select";
import Button from "../ui/Button";
import Spinner from "../ui/Spinner";
import ElapsedTimer from "../ui/ElapsedTimer";

export default function DashboardPage() {
  const [months, setMonths] = useState(3);
  const [process, setProcess] = useState("all");
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingStartedAt, setLoadingStartedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Guards against out-of-order responses: only the latest request may
  // write data/error/loading (months/process can change mid-fetch).
  const reqIdRef = useRef(0);

  const load = useCallback(async (force = false) => {
    const id = ++reqIdRef.current;
    setLoading(true);
    setLoadingStartedAt(Date.now());
    setError(null);
    try {
      const res = await fetchDashboardSummary(months, process, force);
      if (id !== reqIdRef.current) return; // stale response
      setData(res);
    } catch (e) {
      if (id !== reqIdRef.current) return; // stale response
      console.error(e);
      setError("Failed to load dashboard data.");
    } finally {
      if (id === reqIdRef.current) {
        setLoading(false);
        setLoadingStartedAt(null);
      }
    }
  }, [months, process]);

  useEffect(() => { load(false); }, [load]);

  return (
    <main style={styles.container}>
      <PageTitle title="Dashboard" />

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
          {loading ? (
            <>
              <Spinner size={14} /> Refreshing…
            </>
          ) : (
            "🔄 Refresh"
          )}
        </Button>
        {data && <span style={styles.updated}>Updated: {new Date(data.generated_at).toLocaleString()}</span>}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {!data && loading && (
        <div style={{ ...styles.card, ...styles.initialLoadingCard }} aria-busy="true">
          <Spinner size={28} />
          <div aria-live="polite" style={styles.loadingText}>
            {loadingStartedAt != null && <ElapsedTimer startedAt={loadingStartedAt} label="Loading data" />}
          </div>
        </div>
      )}

      {data && (
        <div style={styles.card} aria-busy={loading}>
          <div style={loading ? styles.dimmedWrap : undefined}>
            <SummaryTable rows={data.rows} months={data.period.months} />
          </div>
          {loading && (
            <div style={styles.overlay}>
              <Spinner size={28} />
              <div aria-live="polite" style={styles.loadingText}>
                {loadingStartedAt != null && <ElapsedTimer startedAt={loadingStartedAt} label="Refreshing" />}
              </div>
            </div>
          )}
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
    position: "relative",
  },
  initialLoadingCard: {
    minHeight: 240,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  dimmedWrap: { opacity: 0.45, pointerEvents: "none" },
  overlay: {
    position: "absolute",
    inset: 0,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    background: "rgba(250, 249, 245, 0.55)",
  },
  loadingText: { fontSize: 13, color: "var(--muted)", fontVariantNumeric: "tabular-nums" },
  empty: { color: "var(--muted-soft)", fontSize: 14 },
};
