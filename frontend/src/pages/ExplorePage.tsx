import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { fetchExploreLots } from "../api/client";
import type { ExploreLotsResponse, ProcessData } from "../types";
import YieldChart from "../components/YieldChart";
import LotTable from "../components/explore/LotTable";
import { last8 } from "../utils/tpRev";

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
  const [searchParams] = useSearchParams();
  const sub = searchParams.get("sub") ?? "";
  const navigate = useNavigate();
  const [data, setData] = useState<ExploreLotsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // When `sub` is set we drill into a single sub-process; otherwise the merged
  // major process is shown.
  const label = sub || process;

  useEffect(() => {
    let active = true;
    fetchExploreLots(productId, process, 6, sub || undefined)
      .then((d) => { if (active) setData(d); })
      .catch((e) => { console.error(e); if (active) setError("Failed to load lot data."); });
    return () => { active = false; };
  }, [productId, process, sub]);

  const processData = useMemo(
    () => (data ? toProcessData(data) : null),
    [data]
  );

  return (
    <main style={styles.container}>
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <button onClick={() => navigate("/dashboard")} style={styles.back}>← Back</button>
          <div>
            <div style={styles.breadcrumb}>
              Explore · Lot Drill-down{data?.display_name ? ` · ${data.display_name}` : ""}
            </div>
            <h1 style={styles.title}>{productId} <span style={styles.proc}>/ {label}</span></h1>
          </div>
        </div>
      </header>

      {error && <div style={styles.error}>{error}</div>}
      {data && data.lots.length === 0 && <p style={styles.empty}>No lots found.</p>}
      {data && processData && data.lots.length > 0 && (
        <div style={styles.stack}>
          <YieldChart processName={label} data={processData} />
          <div style={styles.card}>
            <LotTable lots={data.lots} availableBins={data.available_bins} />
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
    background: "var(--warm-white)",
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
  back: {
    padding: "7px 14px",
    cursor: "pointer",
    borderRadius: 8,
    border: "var(--border-whisper)",
    background: "var(--white)",
    color: "var(--gray-700)",
    fontSize: 13,
    fontWeight: 500,
    boxShadow: "var(--shadow-button)",
  },
  breadcrumb: {
    fontSize: 12,
    color: "var(--gray-400)",
    fontWeight: 500,
    letterSpacing: "0.02em",
    marginBottom: 6,
  },
  title: {
    fontSize: 28,
    fontWeight: 700,
    color: "var(--gray-700)",
    letterSpacing: "-0.02em",
    lineHeight: 1.15,
  },
  proc: { color: "var(--gray-400)", fontWeight: 600 },
  stack: { display: "flex", flexDirection: "column", gap: 24 },
  card: {
    background: "var(--white)",
    border: "var(--border-whisper)",
    borderRadius: 12,
    boxShadow: "var(--shadow-card)",
    overflow: "hidden",
  },
  error: {
    background: "rgba(224, 62, 62, 0.08)",
    color: "var(--red)",
    padding: "10px 14px",
    borderRadius: 8,
    marginBottom: 16,
    fontSize: 13,
  },
  empty: { color: "var(--gray-400)", fontSize: 14 },
};
