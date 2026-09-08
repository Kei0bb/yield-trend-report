import { useCallback, useEffect, useRef, useState } from "react";
import { exportWatTrendPdf, fetchWatTrend } from "../../api/client";
import type { WatTrendResponse } from "../../types";
import Button from "../../ui/Button";
import Select from "../../ui/Select";
import { STATUS_COLOR, STATUS_MARK } from "../../theme";
import WatSummaryTable from "./WatSummaryTable";
import WatItemTrendChart from "./WatItemTrendChart";

interface Props {
  productId: string;
}

export default function WatTrendTab({ productId }: Props) {
  const [months, setMonths] = useState(3);
  const [trend, setTrend] = useState<WatTrendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Guards against out-of-order responses: only the latest request may write
  // state when product or period changes mid-fetch (same idiom as
  // WatSummaryTab's loadSummary).
  const reqIdRef = useRef(0);

  const loadTrend = useCallback(async () => {
    if (!productId) {
      setTrend(null);
      return;
    }
    const id = ++reqIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWatTrend(productId, months);
      if (id !== reqIdRef.current) return; // stale response
      setTrend(res);
    } catch (e) {
      if (id !== reqIdRef.current) return; // stale response
      console.error("Failed to load WAT trend:", e);
      setError("Failed to load WAT trend.");
      setTrend(null);
    } finally {
      if (id === reqIdRef.current) setLoading(false);
    }
  }, [productId, months]);

  useEffect(() => { void loadTrend(); }, [loadTrend]);

  const handleExport = async () => {
    if (!productId) return;
    setExporting(true);
    try {
      await exportWatTrendPdf(productId, months);
    } catch (e) {
      console.error("WAT trend PDF export failed:", e);
      setError("PDF export failed.");
    } finally {
      setExporting(false);
    }
  };

  const reds = trend?.items.filter((i) => i.status === "red").length ?? 0;
  const yellows = trend?.items.filter((i) => i.status === "yellow").length ?? 0;
  const latest = trend?.lots[0]?.last_measured ?? "—";

  return (
    <div>
      <div style={styles.toolbar}>
        <label style={styles.field}>
          <span style={styles.fieldLabel}>Period</span>
          <Select value={String(months)} onChange={(e) => setMonths(Number(e.target.value))}>
            <option value="1">Last 1 month</option>
            <option value="3">Last 3 months</option>
            <option value="6">Last 6 months</option>
          </Select>
        </label>

        <Button onClick={handleExport} disabled={!trend || loading || exporting}>
          {exporting ? "Generating…" : "Export PDF"}
        </Button>
        {exporting && <span style={styles.hint}>One chart per item — this takes a while</span>}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading && <div style={styles.hint}>Loading…</div>}

      {!loading && trend && trend.items.length === 0 && (
        <div style={styles.empty}>No WAT data for this period.</div>
      )}

      {!loading && trend && trend.items.length > 0 && (
        <>
          <div style={styles.header}>
            <strong style={styles.period}>{trend.start_date} — {latest}</strong>
            <span>{trend.lots.length} lots</span>
            <span>{trend.items.length} items</span>
            <span style={styles.counts}>
              <span style={{ color: STATUS_COLOR.red, fontWeight: 600 }}>
                {STATUS_MARK.red} {reds}
              </span>
              <span style={{ color: STATUS_COLOR.yellow, fontWeight: 600 }}>
                {STATUS_MARK.yellow} {yellows}
              </span>
            </span>
          </div>
          <WatSummaryTable
            items={trend.items}
            renderChart={(item) => (
              <WatItemTrendChart
                title={`${item.item_name}${item.unit ? ` [${item.unit}]` : ""}`}
                points={item.lot_series.map((p) => ({
                  label: p.lot_id,
                  mean: p.mean,
                  sigma: p.sigma,
                  color: STATUS_COLOR[p.status],
                }))}
                xTitle="Lot"
                specLow={item.spec_low}
                specHigh={item.spec_high}
                categoryAxis
                hoverPrefix="Lot "
              />
            )}
          />
        </>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: { display: "flex", alignItems: "center", gap: 18, marginBottom: 20, flexWrap: "wrap" },
  field: { display: "inline-flex", alignItems: "center", gap: 8 },
  fieldLabel: {
    fontSize: 11, fontWeight: 600, textTransform: "uppercase",
    letterSpacing: "0.06em", color: "var(--muted-soft)",
  },
  hint: { fontSize: 12, color: "var(--muted-soft)" },
  empty: {
    padding: "28px 0", textAlign: "center",
    color: "var(--muted-soft)", fontSize: 13,
  },
  error: {
    background: "rgba(198, 69, 69, 0.08)", color: "var(--error)",
    padding: "10px 14px", borderRadius: "var(--radius-control)",
    marginBottom: 16, fontSize: 13,
  },
  header: {
    display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap",
    padding: "12px 16px", marginBottom: 16,
    background: "var(--surface-card)", border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    fontSize: 13, color: "var(--muted)",
  },
  period: { color: "var(--ink)", fontSize: 14 },
  counts: { display: "inline-flex", gap: 14, marginLeft: "auto" },
};
