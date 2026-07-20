import { useEffect, useState } from "react";
import ReportView from "../components/ReportView";
import ErrorBanner from "../components/ErrorBanner";
import { fetchReportProducts, fetchHealth, fetchYieldData, exportPdf, fetchProcessUnits } from "../api/client";
import type { Product, YieldRequest, YieldResponse } from "../types";
import PageTitle from "../ui/PageTitle";
import Select from "../ui/Select";
import Button from "../ui/Button";

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
  const [units, setUnits] = useState<{ family: string; label: string }[]>([]);
  const [processes, setProcesses] = useState<string[]>([]);
  const [isMock, setIsMock] = useState<boolean | null>(null);

  const [data, setData] = useState<YieldResponse | null>(null);
  const [request, setRequest] = useState<YieldRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReportProducts().then((list) => {
      setProducts(list);
      if (list.length > 0) setProductId(list[0].product_id);
    });
    fetchHealth().then((h) => setIsMock(h.mock)).catch(() => setIsMock(null));
  }, []);

  useEffect(() => {
    if (!productId) {
      setUnits([]);
      setProcesses([]);
      return;
    }
    fetchProcessUnits(productId)
      .then((list) => {
        setUnits(list);
        setProcesses(list.map((u) => u.label));
      })
      .catch((err) => {
        console.error("Failed to fetch process units:", err);
        setUnits([]);
        setProcesses([]);
      });
  }, [productId]);

  const toggleProcess = (p: string) =>
    setProcesses((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );

  const buildRequest = (): YieldRequest => {
    const now = new Date();
    // Order by the units array (config order from /process-units) so toggling
    // chips can't scramble the chart order — the Report renders in this order.
    const orderedProcesses = units.length
      ? units.map((u) => u.label).filter((label) => processes.includes(label))
      : processes;
    return {
      products: [productId],
      start_month: formatYM(addMonths(now, -2)),  // fixed 3-month window ending this month
      end_month: formatYM(now),
      processes: orderedProcesses,
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
        <PageTitle breadcrumb="Reports · Yield Trend" title="Report" />

        <div style={styles.toolbar}>
          <label style={styles.field}>
            <span style={styles.fieldLabel}>Product</span>
            <Select value={productId} onChange={(e) => setProductId(e.target.value)}>
              {products.map((p) => (
                <option key={p.product_id} value={p.product_id}>
                  {p.product_id}{p.display_name && p.display_name !== p.product_id ? ` — ${p.display_name}` : ""}
                </option>
              ))}
            </Select>
          </label>

          <div style={styles.field}>
            <span style={styles.fieldLabel}>Process</span>
            <div style={styles.chipGroup}>
              {units.map((u) => {
                const active = processes.includes(u.label);
                return (
                  <button
                    key={u.label}
                    type="button"
                    onClick={() => toggleProcess(u.label)}
                    style={{ ...styles.chip, ...(active ? styles.chipActive : {}) }}
                  >
                    {u.label}
                  </button>
                );
              })}
            </div>
          </div>

          <Button variant="primary" onClick={handleGenerate} disabled={disabled}>
            {loading ? "Loading…" : "Generate Report"}
          </Button>
          <Button onClick={() => exportPdf(buildRequest())} disabled={data === null || disabled}>
            Export PDF
          </Button>

          <span style={styles.mock}>
            <span style={{ ...styles.mockDot, background: isMock === false ? "var(--success)" : "var(--muted-soft)" }} />
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
    background: "var(--canvas)",
    minWidth: 0,
  },
  toolbar: { display: "flex", alignItems: "center", gap: 18, marginBottom: 24, flexWrap: "wrap" },
  field: { display: "inline-flex", alignItems: "center", gap: 8 },
  fieldLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted-soft)",
  },
  chipGroup: { display: "flex", gap: 6, flexWrap: "wrap" },
  chip: {
    padding: "6px 14px",
    borderRadius: "var(--radius-pill)",
    border: "var(--hairline)",
    background: "var(--surface-card)",
    color: "var(--muted)",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
  },
  chipActive: {
    background: "var(--surface-soft)",
    color: "var(--ink)",
    border: "1px solid rgba(204, 120, 92, 0.45)",
  },
  mock: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    color: "var(--muted-soft)",
    marginLeft: "auto",
  },
  mockDot: { width: 6, height: 6, borderRadius: "50%", display: "inline-block" },
};
