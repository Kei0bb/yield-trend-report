import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import TopNav from "./components/TopNav";
import ReportPage from "./pages/ReportPage";
import DashboardPage from "./pages/DashboardPage";
import ExplorePage from "./pages/ExplorePage";

export default function App() {
  return (
    <BrowserRouter>
      <div style={styles.app}>
        <TopNav />
        <div style={styles.body}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/report" element={<ReportPage />} />
            <Route path="/explore/:nickname/:process" element={<ExplorePage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    display: "flex",
    flexDirection: "column",
    minHeight: "100vh",
    background: "var(--warm-white)",
    fontFamily: "var(--font-sans)",
    color: "var(--gray-700)",
  },
  body: { display: "flex", flex: 1, minWidth: 0 },
};
