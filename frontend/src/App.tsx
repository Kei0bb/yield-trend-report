import { useState } from "react";
import Sidebar from "./components/Sidebar";
import ReportView from "./components/ReportView";
import ErrorBanner from "./components/ErrorBanner";
import { fetchYieldData } from "./api/client";
import type { YieldRequest, YieldResponse } from "./types";

export default function App() {
  const [data, setData] = useState<YieldResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentRequest, setCurrentRequest] = useState<YieldRequest | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async (req: YieldRequest) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchYieldData(req);
      setData(res);
      setCurrentRequest(req);
    } catch (err) {
      console.error("Failed to fetch yield data:", err);
      setError("データ取得に失敗しました。バックエンドが起動しているか確認してください。");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.app}>
      <Sidebar
        onGenerate={handleGenerate}
        loading={loading}
        canPrint={data !== null}
      />
      <div style={styles.main}>
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
        <ReportView data={data} request={currentRequest} />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    display: "flex",
    minHeight: "100vh",
    background: "var(--warm-white)",
    fontFamily: "var(--font-sans)",
    color: "var(--gray-700)",
  },
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
  },
};
