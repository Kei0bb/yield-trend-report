import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { fetchExploreLots } from "../api/client";
import type { ExploreLotsResponse } from "../types";
import LotTrendChart from "../components/explore/LotTrendChart";
import LotTable from "../components/explore/LotTable";
import { getLotIdFormat, setLotIdFormat, type LotIdFormat } from "../utils/formatLotId";

export default function ExplorePage() {
  const { nickname = "", process = "" } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<ExploreLotsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [format, setFormat] = useState<LotIdFormat>(getLotIdFormat());

  useEffect(() => {
    let active = true;
    fetchExploreLots(nickname, process, 6)
      .then((d) => { if (active) setData(d); })
      .catch((e) => { console.error(e); if (active) setError("ロットデータの取得に失敗しました。"); });
    return () => { active = false; };
  }, [nickname, process]);

  const changeFormat = (f: LotIdFormat) => { setFormat(f); setLotIdFormat(f); };

  return (
    <main style={{ flex: 1, padding: "28px 40px", overflowY: "auto" }}>
      <div style={styles.header}>
        <button onClick={() => navigate("/dashboard")} style={styles.back}>← Dashboard</button>
        <h2 style={{ margin: 0 }}>{nickname} / {process}</h2>
        <label style={{ marginLeft: "auto", fontSize: 13 }}>
          Lot ID 表示:
          <select value={format} onChange={(e) => changeFormat(e.target.value as LotIdFormat)} style={{ marginLeft: 6 }}>
            <option value="raw">実ロット番号</option>
            <option value="date">日付</option>
            <option value="yearweek">年週</option>
          </select>
        </label>
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {data && data.lots.length === 0 && <p>該当するロットがありません。</p>}
      {data && data.lots.length > 0 && (
        <>
          <LotTrendChart lots={data.lots} format={format} />
          <LotTable lots={data.lots} availableBins={data.available_bins} format={format} />
        </>
      )}
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  header: { display: "flex", alignItems: "center", gap: 16, marginBottom: 16 },
  back: { padding: "6px 12px", cursor: "pointer", borderRadius: 8, border: "1px solid #d8d4c8", background: "#fff" },
  error: { background: "#fdecea", color: "#b13a2a", padding: "10px 14px", borderRadius: 8, marginBottom: 16 },
};
