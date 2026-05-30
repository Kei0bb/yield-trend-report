import { useEffect, useState, useCallback } from "react";
import { fetchDashboardSummary } from "../api/client";
import type { DashboardSummaryResponse } from "../types";
import SummaryTable from "../components/dashboard/SummaryTable";

export default function DashboardPage() {
  const [months, setMonths] = useState(6);
  const [process, setProcess] = useState("all");
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchDashboardSummary(months, process));
    } catch (e) {
      console.error(e);
      setError("ダッシュボードデータの取得に失敗しました。");
    } finally {
      setLoading(false);
    }
  }, [months, process]);

  useEffect(() => { load(); }, [load]);

  return (
    <main style={{ flex: 1, padding: "28px 40px", overflowY: "auto" }}>
      <div style={styles.toolbar}>
        <label>期間:
          <select value={months} onChange={(e) => setMonths(Number(e.target.value))} style={styles.select}>
            <option value={3}>過去3ヶ月</option>
            <option value={6}>過去6ヶ月</option>
            <option value={12}>過去12ヶ月</option>
          </select>
        </label>
        <label>プロセス:
          <select value={process} onChange={(e) => setProcess(e.target.value)} style={styles.select}>
            <option value="all">All</option>
            <option value="CP">CP</option>
            <option value="FT">FT</option>
          </select>
        </label>
        <button onClick={load} disabled={loading} style={styles.refresh}>
          {loading ? "更新中…" : "🔄 更新"}
        </button>
        {data && <span style={styles.updated}>最終更新: {new Date(data.generated_at).toLocaleString()}</span>}
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {data && <SummaryTable rows={data.rows} />}
      {data && data.rows.length === 0 && !loading && <p>データがありません。</p>}
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: { display: "flex", alignItems: "center", gap: 16, marginBottom: 20, flexWrap: "wrap" },
  select: { marginLeft: 6, padding: "4px 8px" },
  refresh: { padding: "6px 14px", cursor: "pointer", borderRadius: 8, border: "1px solid #d8d4c8", background: "#fff" },
  updated: { fontSize: 12, color: "#888", marginLeft: "auto" },
  error: { background: "#fdecea", color: "#b13a2a", padding: "10px 14px", borderRadius: 8, marginBottom: 16 },
};
