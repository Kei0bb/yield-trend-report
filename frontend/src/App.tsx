import { useState } from "react";
import Sidebar from "./components/Sidebar";
import ReportView from "./components/ReportView";
import { fetchYieldData, exportPdf } from "./api/client";
import type { YieldRequest, YieldResponse } from "./types";

export default function App() {
  const [data, setData] = useState<YieldResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentRequest, setCurrentRequest] = useState<YieldRequest | null>(null);

  const handleGenerate = async (req: YieldRequest) => {
    setLoading(true);
    try {
      const res = await fetchYieldData(req);
      setData(res);
      setCurrentRequest(req);
    } catch (err) {
      console.error("Failed to fetch yield data:", err);
      alert("Failed to fetch data. Check if the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  const handleExportPdf = async (req: YieldRequest) => {
    setLoading(true);
    try {
      await exportPdf(req);
    } catch (err) {
      console.error("Failed to export PDF:", err);
      alert("Failed to export PDF. Check if the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.app}>
      <Sidebar
        onGenerate={handleGenerate}
        onExportPdf={handleExportPdf}
        loading={loading}
      />
      <ReportView data={data} request={currentRequest} />
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
};
