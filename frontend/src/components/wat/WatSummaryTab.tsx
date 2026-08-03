import { useCallback, useEffect, useRef, useState } from "react";
import { exportWatPdf, fetchWatLots, fetchWatSummary } from "../../api/client";
import type { WatLotInfo, WatSummaryResponse } from "../../types";
import Button from "../../ui/Button";
import Select from "../../ui/Select";
import { STATUS_MARK } from "../../theme";

interface Props {
  productId: string;
}

export default function WatSummaryTab({ productId }: Props) {
  const [months, setMonths] = useState(3);
  const [lots, setLots] = useState<WatLotInfo[]>([]);
  const [lotId, setLotId] = useState("");
  const [summary, setSummary] = useState<WatSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Lot list follows product + period. Reset the selection when it reloads so
  // a stale lot_id from a previous product is never queried.
  useEffect(() => {
    if (!productId) {
      setLots([]);
      setLotId("");
      return;
    }
    let cancelled = false;
    setError(null);
    fetchWatLots(productId, months)
      .then((res) => {
        if (cancelled) return;
        setLots(res.lots);
        setLotId(res.lots.length > 0 ? res.lots[0].lot_id : "");
      })
      .catch(() => {
        if (cancelled) return;
        setLots([]);
        setLotId("");
        setError("Failed to load WAT lots.");
      });
    return () => { cancelled = true; };
  }, [productId, months]);

  // Guards loadSummary against out-of-order responses: only the latest
  // request may write state when lotId changes mid-fetch (see WaferMapPage's
  // loadLots for the same idiom).
  const summaryReqIdRef = useRef(0);

  const loadSummary = useCallback(async () => {
    if (!productId || !lotId) return;
    const id = ++summaryReqIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWatSummary(productId, lotId);
      if (id !== summaryReqIdRef.current) return; // stale response
      setSummary(res);
    } catch (e) {
      if (id !== summaryReqIdRef.current) return; // stale response
      console.error("Failed to load WAT summary:", e);
      setError("Failed to load WAT summary.");
      setSummary(null);
    } finally {
      if (id === summaryReqIdRef.current) setLoading(false);
    }
  }, [productId, lotId]);

  useEffect(() => { void loadSummary(); }, [loadSummary]);

  const handleExport = async () => {
    if (!productId || !lotId) return;
    setExporting(true);
    try {
      await exportWatPdf(productId, lotId);
    } catch (e) {
      console.error("WAT PDF export failed:", e);
      setError("PDF export failed.");
    } finally {
      setExporting(false);
    }
  };

  const reds = summary?.items.filter((i) => i.status === "red").length ?? 0;
  const yellows = summary?.items.filter((i) => i.status === "yellow").length ?? 0;

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

        <label style={styles.field}>
          <span style={styles.fieldLabel}>Lot</span>
          <Select value={lotId} onChange={(e) => setLotId(e.target.value)}>
            {lots.length === 0 && <option value="">No lots</option>}
            {lots.map((l) => (
              <option key={l.lot_id} value={l.lot_id}>
                {l.lot_id} — {l.last_measured}
              </option>
            ))}
          </Select>
        </label>

        <Button onClick={handleExport} disabled={!lotId || loading || exporting}>
          {exporting ? "Generating…" : "Export PDF"}
        </Button>
        {exporting && <span style={styles.hint}>24 charts — this takes a while</span>}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading && <div style={styles.hint}>Loading…</div>}

      {!loading && summary && summary.items.length === 0 && (
        <div style={styles.empty}>No WAT data for this lot.</div>
      )}

      {!loading && summary && summary.items.length > 0 && (
        <>
          <div style={styles.lotHeader}>
            <strong style={styles.lotId}>{summary.lot_id}</strong>
            <span>{summary.measured_date || "—"}</span>
            <span>{summary.wafer_count} wafers</span>
            <span>{summary.items.length} items</span>
            <span style={styles.counts}>
              <span style={styles.red}>{STATUS_MARK.red} {reds}</span>
              <span style={styles.yellow}>{STATUS_MARK.yellow} {yellows}</span>
            </span>
          </div>
          {/* Task 11 adds WatSummaryTable, Task 12 adds WatScatterGrid */}
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
  lotHeader: {
    display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap",
    padding: "12px 16px", marginBottom: 16,
    background: "var(--surface-card)", border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    fontSize: 13, color: "var(--muted)",
  },
  lotId: { color: "var(--ink)", fontSize: 14 },
  counts: { display: "inline-flex", gap: 14, marginLeft: "auto" },
  red: { color: "var(--error)", fontWeight: 600 },
  yellow: { color: "var(--warning)", fontWeight: 600 },
};
