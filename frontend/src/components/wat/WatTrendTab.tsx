import { useRef, useState } from "react";
import { exportWatTrendPdf, fetchWatTrend } from "../../api/client";
import type { WatTrendResponse } from "../../types";
import Button from "../../ui/Button";
import Select from "../../ui/Select";
import { STATUS_COLOR, STATUS_MARK, STATUS_PLOT_COLOR } from "../../theme";
import WatSummaryTable from "./WatSummaryTable";
import WatItemTrendChart from "./WatItemTrendChart";

interface Props {
  productId: string;
}

export default function WatTrendTab({ productId }: Props) {
  const [months, setMonths] = useState(3);
  const [exporting, setExporting] = useState(false);

  // Nothing is fetched until Generate. Every result, pending request and
  // error is tagged with the conditions it was made under and shown only
  // while those are still the current conditions — so a late response can
  // never paint one period's data under another period's toolbar.
  const key = `${productId}|${months}`;
  const [result, setResult] = useState<{ key: string; trend: WatTrendResponse } | null>(null);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [failure, setFailure] = useState<{ key: string; message: string } | null>(null);

  // Changing product or period clears the previous result (React's
  // "adjust state during render" pattern — no effect, no flash of stale data).
  const [prevKey, setPrevKey] = useState(key);
  if (prevKey !== key) {
    setPrevKey(key);
    setResult(null);
    setFailure(null);
  }

  const trend = result?.key === key ? result.trend : null;
  const loading = pendingKey === key;
  const error = failure?.key === key ? failure.message : null;

  // Only the latest Generate may write state (out-of-order responses).
  const reqIdRef = useRef(0);

  const handleGenerate = async () => {
    if (!productId) return;
    const id = ++reqIdRef.current;
    const reqKey = key;
    setPendingKey(reqKey);
    setFailure(null);
    try {
      const res = await fetchWatTrend(productId, months);
      if (id !== reqIdRef.current) return; // stale response
      setResult({ key: reqKey, trend: res });
    } catch (e) {
      if (id !== reqIdRef.current) return; // stale response
      console.error("Failed to load WAT trend:", e);
      setFailure({ key: reqKey, message: "Failed to load WAT trend." });
      setResult(null);
    } finally {
      if (id === reqIdRef.current) setPendingKey(null);
    }
  };

  const handleExport = async () => {
    if (!productId || !trend) return;
    const reqKey = key;
    setExporting(true);
    try {
      await exportWatTrendPdf(productId, months);
    } catch (e) {
      console.error("WAT trend PDF export failed:", e);
      setFailure({ key: reqKey, message: "PDF export failed." });
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

        <Button variant="primary" onClick={handleGenerate} disabled={!productId || loading}>
          {loading ? "Loading…" : "Generate"}
        </Button>

        <Button onClick={handleExport} disabled={!trend || loading || exporting}>
          {exporting ? "Generating…" : "Export PDF"}
        </Button>
        {exporting && <span style={styles.hint}>One chart per item — this takes a while</span>}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading && <div style={styles.hint}>Loading…</div>}

      {!loading && !trend && !error && (
        <div style={styles.empty}>Choose a period and press Generate.</div>
      )}

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
                  color: STATUS_PLOT_COLOR[p.status],
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
