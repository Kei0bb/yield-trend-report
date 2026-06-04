import { useEffect, useState } from "react";
import ReportView from "../components/ReportView";
import ErrorBanner from "../components/ErrorBanner";
import { fetchProducts, fetchHealth, fetchYieldData, exportPdf } from "../api/client";
import type { Product, YieldRequest, YieldResponse } from "../types";

const PROCESSES = ["CP", "FT", "SLT"];

function formatYM(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

function addMonths(d: Date, n: number): Date {
  const r = new Date(d);
  r.setMonth(r.getMonth() + n);
  return r;
}

export default function ReportPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState("");
  const [processes, setProcesses] = useState<string[]>(["CP", "FT", "SLT"]);
  const [isMock, setIsMock] = useState<boolean | null>(null);

  const [data, setData] = useState<YieldResponse | null>(null);
  const [request, setRequest] = useState<YieldRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProducts().then((list) => {
      setProducts(list);
      if (list.length > 0) setProductId(list[0].product_id);
    });
    fetchHealth().then((h) => setIsMock(h.mock)).catch(() => setIsMock(null));
  }, []);

  const toggleProcess = (p: string) =>
    setProcesses((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );

  const buildRequest = (): YieldRequest => {
    const now = new Date();
    return {
      products: [productId],
      start_month: formatYM(addMonths(now, -2)),  // fixed 3-month window ending this month
      end_month: formatYM(now),
      processes,
    };
  };

  const disabled = loading || !productId || processes.length === 0;

  const handleGenerate = async () => {
    const req = buildRequest();
    setLoading(true);
    setError(null);
    try {
      const res = await fetchYieldData(req);
      setData(res);
      setRequest(req);
    } catch (err) {
      console.error("Failed to fetch yield data:", err);
      setError("Failed to load data. Please check that the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
      <main style={styles.container}>
        <header style={styles.header}>
          <div style={styles.breadcrumb}>Reports · Yield Trend</div>
          <h1 style={styles.title}>Report</h1>
        </header>

        <div style={styles.toolbar}>
          <label style={styles.field}>
            <span style={styles.fieldLabel}>Product</span>
            <select value={productId} onChange={(e) => setProductId(e.target.value)} style={styles.select}>
              {products.map((p) => (
                <option key={p.product_id} value={p.product_id}>
                  {p.product_id}{p.display_name && p.display_name !== p.product_id ? ` — ${p.display_name}` : ""}
                </option>
              ))}
            </select>
          </label>

          <div style={styles.field}>
            <span style={styles.fieldLabel}>Process</span>
            <div style={styles.chipGroup}>
              {PROCESSES.map((p) => {
                const active = processes.includes(p);
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => toggleProcess(p)}
                    style={{ ...styles.chip, ...(active ? styles.chipActive : {}) }}
                  >
                    {p}
                  </button>
                );
              })}
            </div>
          </div>

          <button onClick={handleGenerate} disabled={disabled} style={{ ...styles.primaryBtn, ...(disabled ? styles.btnDisabled : {}) }}>
            {loading ? "Loading…" : "Generate Report"}
          </button>
          <button
            onClick={() => exportPdf(buildRequest())}
            disabled={data === null || disabled}
            style={{ ...styles.secondaryBtn, ...(data === null || disabled ? styles.btnDisabled : {}) }}
          >
            Export PDF
          </button>

          <span style={styles.mock}>
            <span style={{ ...styles.mockDot, background: isMock === false ? "var(--notion-blue)" : "var(--green)" }} />
            {isMock === null ? "Connecting…" : isMock ? "Mock data" : "Live DB"}
          </span>
        </div>

        <ReportView data={data} request={request} />
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { flex: 1, display: "flex", flexDirection: "column", minWidth: 0 },
  container: {
    flex: 1,
    padding: "40px 56px 56px",
    overflowY: "auto",
    background: "var(--warm-white)",
    minWidth: 0,
  },
  header: { marginBottom: 24 },
  breadcrumb: {
    fontSize: 12,
    color: "var(--gray-400)",
    fontWeight: 500,
    letterSpacing: "0.02em",
    marginBottom: 8,
  },
  title: {
    fontSize: 32,
    fontWeight: 700,
    color: "var(--gray-700)",
    letterSpacing: "-0.025em",
    lineHeight: 1.15,
  },
  toolbar: { display: "flex", alignItems: "center", gap: 18, marginBottom: 24, flexWrap: "wrap" },
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
  chipGroup: { display: "flex", gap: 6, flexWrap: "wrap" },
  chip: {
    padding: "6px 14px",
    borderRadius: 999,
    border: "var(--border-whisper)",
    background: "var(--white)",
    color: "var(--gray-500)",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
  },
  chipActive: {
    background: "var(--badge-bg)",
    color: "var(--badge-text)",
    border: "1px solid rgba(9, 127, 232, 0.3)",
  },
  primaryBtn: {
    background: "var(--notion-blue)",
    color: "var(--white)",
    border: "none",
    borderRadius: 8,
    padding: "8px 18px",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
    boxShadow: "var(--shadow-button)",
  },
  secondaryBtn: {
    background: "var(--white)",
    color: "var(--gray-700)",
    border: "var(--border-whisper)",
    borderRadius: 8,
    padding: "8px 18px",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
    boxShadow: "var(--shadow-button)",
  },
  btnDisabled: { opacity: 0.5, cursor: "not-allowed" },
  mock: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    color: "var(--gray-400)",
    marginLeft: "auto",
  },
  mockDot: { width: 6, height: 6, borderRadius: "50%", display: "inline-block" },
};
