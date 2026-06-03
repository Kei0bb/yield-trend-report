import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { fetchExploreLots } from "../api/client";
import type { ExploreLotsResponse, ProcessData } from "../types";
import YieldChart from "../components/YieldChart";
import LotTable from "../components/explore/LotTable";
import { formatLotId, getLotIdFormat, setLotIdFormat, type LotIdFormat } from "../utils/formatLotId";

/** Map the lot-granular Explore response into the Report-style ProcessData
 *  (lots = x-axis labels, yield_avg = yield line, fail_bins = stacked bars),
 *  so the trend view is identical to the Report tab's YieldChart. */
function toProcessData(data: ExploreLotsResponse, format: LotIdFormat): ProcessData {
  return {
    lots: data.lots.map((l) => formatLotId(l.lot_id, l.lot_date, format)),
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
  const navigate = useNavigate();
  const [data, setData] = useState<ExploreLotsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [format, setFormat] = useState<LotIdFormat>(getLotIdFormat());

  useEffect(() => {
    let active = true;
    fetchExploreLots(productId, process, 6)
      .then((d) => { if (active) setData(d); })
      .catch((e) => { console.error(e); if (active) setError("ロットデータの取得に失敗しました。"); });
    return () => { active = false; };
  }, [productId, process]);

  const changeFormat = (f: LotIdFormat) => { setFormat(f); setLotIdFormat(f); };

  const processData = useMemo(
    () => (data ? toProcessData(data, format) : null),
    [data, format]
  );

  return (
    <main style={styles.container}>
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <button onClick={() => navigate("/dashboard")} style={styles.back}>← Dashboard</button>
          <div>
            <div style={styles.breadcrumb}>
              Explore · Lot Drill-down{data?.display_name ? ` · ${data.display_name}` : ""}
            </div>
            <h1 style={styles.title}>{productId} <span style={styles.proc}>/ {process}</span></h1>
          </div>
        </div>
        <label style={styles.field}>
          <span style={styles.fieldLabel}>Lot ID 表示</span>
          <select value={format} onChange={(e) => changeFormat(e.target.value as LotIdFormat)} style={styles.select}>
            <option value="raw">実ロット番号</option>
            <option value="date">日付</option>
            <option value="yearweek">年週</option>
          </select>
        </label>
      </header>

      {error && <div style={styles.error}>{error}</div>}
      {data && data.lots.length === 0 && <p style={styles.empty}>該当するロットがありません。</p>}
      {data && processData && data.lots.length > 0 && (
        <div style={styles.stack}>
          <YieldChart processName={process} data={processData} />
          <div style={styles.card}>
            <LotTable lots={data.lots} availableBins={data.available_bins} format={format} />
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
