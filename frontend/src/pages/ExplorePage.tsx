import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { fetchExploreLots } from "../api/client";
import type { ExploreLotsResponse, ProcessData } from "../types";
import YieldChart from "../components/YieldChart";
import LotTable from "../components/explore/LotTable";
import { last8 } from "../utils/tpRev";
import Button from "../ui/Button";
import Select from "../ui/Select";

/** Map the lot-granular Explore response into the Report-style ProcessData
 *  (lots = x-axis labels, yield_avg = yield line, fail_bins = stacked bars),
 *  so the trend view is identical to the Report tab's YieldChart.
 *
 *  A lot_id can repeat when split across multiple TP revs, so x-axis labels
 *  are disambiguated with the rev's last-8 chars whenever a lot_id occurs
 *  more than once. */
function toProcessData(data: ExploreLotsResponse): ProcessData {
  const counts: Record<string, number> = {};
  data.lots.forEach((l) => { counts[l.lot_id] = (counts[l.lot_id] || 0) + 1; });
  const labelFor = (l: typeof data.lots[number]) =>
    counts[l.lot_id] > 1 && l.test_program_rev ? `${l.lot_id} (${last8(l.test_program_rev)})` : l.lot_id;

  return {
    lots: data.lots.map(labelFor),
    yield_avg: data.lots.map((l) => l.yield_pct),
    fail_bins: Object.fromEntries(
      data.available_bins.map((bin) => [
        bin,
        data.lots.map((l) => l.bin_breakdown.find((x) => x.bin_name === bin)?.percent ?? 0),
      ])
    ),
  };
}

export default function ExplorePage() {
  const { productId = "", process = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const sub = searchParams.get("sub") ?? "";
  // Period is carried over from the Dashboard's selector via ?months=;
  // fall back to 6 for direct links / legacy URLs.
  const monthsParam = parseInt(searchParams.get("months") ?? "", 10);
  const months = [1, 3, 6].includes(monthsParam) ? monthsParam : 6;
  const navigate = useNavigate();
  const [data, setData] = useState<ExploreLotsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // When `sub` is set we drill into a single sub-process; otherwise the merged
  // major process is shown.
  const label = sub || process;

  useEffect(() => {
    let active = true;
    fetchExploreLots(productId, process, months, sub || undefined)
      .then((d) => { if (active) { setData(d); setError(null); } })
      .catch((e) => { console.error(e); if (active) setError("Failed to load lot data."); });
    return () => { active = false; };
  }, [productId, process, sub, months]);

  const processData = useMemo(
    () => (data ? toProcessData(data) : null),
    [data]
  );

  return (
    <main style={styles.container}>
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <Button onClick={() => navigate("/dashboard")}>← Back</Button>
          <div>
            {/* display_name rode along in the removed breadcrumb and is shown
                nowhere else on this page, so it moves beside the title —
                matching how the Dashboard and Report show the product name. */}
            <h1 style={styles.title}>
              {productId} <span style={styles.proc}>/ {label}</span>
              {data?.display_name && data.display_name !== productId && (
                <span style={styles.displayName}>{data.display_name}</span>
              )}
            </h1>
          </div>
        </div>
        <label style={styles.field}>
          <span style={styles.fieldLabel}>Period</span>
          <Select
            value={String(months)}
            onChange={(e) => {
              const next = new URLSearchParams(searchParams);
              next.set("months", e.target.value);
              setSearchParams(next, { replace: true });
            }}
          >
            <option value="1">Last 1 month</option>
            <option value="3">Last 3 months</option>
            <option value="6">Last 6 months</option>
          </Select>
        </label>
      </header>

      {error && <div style={styles.error}>{error}</div>}
      {data && data.lots.length === 0 && <p style={styles.empty}>No lots found.</p>}
      {data && processData && data.lots.length > 0 && (
        <div style={styles.stack}>
          <YieldChart processName={label} data={processData} target={data.target} />
          <div style={styles.card}>
            <LotTable
              lots={data.lots}
              availableBins={data.available_bins}
              productId={productId}
              process={process}
              sub={sub || undefined}
              months={months}
            />
          </div>
        </div>
      )}
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
  header: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 16,
    marginBottom: 24,
    flexWrap: "wrap",
  },
  headerLeft: { display: "flex", alignItems: "center", gap: 16 },
  field: { display: "inline-flex", alignItems: "center", gap: 8 },
  fieldLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted-soft)",
  },
  title: {
    fontSize: 26,
    fontWeight: 700,
    color: "var(--ink)",
    letterSpacing: "-0.02em",
    lineHeight: 1.2,
  },
  proc: { color: "var(--muted-soft)", fontWeight: 500 },
  displayName: {
    marginLeft: 10,
    fontSize: 13,
    fontWeight: 500,
    color: "var(--muted-soft)",
    letterSpacing: 0,
  },
  stack: { display: "flex", flexDirection: "column", gap: 24 },
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    overflow: "hidden",
  },
  error: {
    background: "rgba(198, 69, 69, 0.08)",
    color: "var(--error)",
    padding: "10px 14px",
    borderRadius: "var(--radius-control)",
    marginBottom: 16,
    fontSize: 13,
  },
  empty: { color: "var(--muted-soft)", fontSize: 14 },
};
