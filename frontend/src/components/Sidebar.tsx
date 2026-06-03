import { useEffect, useState } from "react";
import { fetchProducts, fetchHealth, exportPdf } from "../api/client";
import type { YieldRequest } from "../types";

interface SidebarProps {
  onGenerate: (req: YieldRequest) => void;
  loading: boolean;
  canPrint: boolean;
}

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

export default function Sidebar({ onGenerate, loading, canPrint }: SidebarProps) {
  const [products, setProducts] = useState<string[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<string>("");
  const [selectedProcesses, setSelectedProcesses] = useState<string[]>(["CP", "FT", "SLT"]);
  const [isMock, setIsMock] = useState<boolean | null>(null);

  useEffect(() => {
    fetchProducts().then((list) => {
      setProducts(list);
      if (list.length > 0) setSelectedProduct(list[0]);
    });
    fetchHealth().then((h) => setIsMock(h.mock)).catch(() => setIsMock(null));
  }, []);

  const toggleProcess = (p: string) =>
    setSelectedProcesses((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );

  const buildRequest = (): YieldRequest => {
    const now = new Date();
    return {
      products: [selectedProduct],
      start_month: formatYM(addMonths(now, -2)),  // 3-month window ending this month
      end_month: formatYM(now),
      processes: selectedProcesses,
    };
  };

  const disabled = loading || !selectedProduct || selectedProcesses.length === 0;

  return (
    <aside style={styles.sidebar}>
      <div style={styles.brand}>
        <img
          src="/logo.png"
          alt="Logo"
          style={styles.brandLogo}
          onError={(e) => {
            // Logo file missing — fall back to a styled "Y" mark.
            const img = e.currentTarget;
            const fallback = img.nextElementSibling as HTMLElement | null;
            img.style.display = "none";
            if (fallback) fallback.style.display = "flex";
          }}
        />
        <div style={{ ...styles.brandMark, display: "none" }}>Y</div>
        <div>
          <div style={styles.brandTitle}>Yield Trend</div>
          <div style={styles.brandSub}>Report Generator</div>
        </div>
      </div>

      {/* ── Product ────────────────────────────────────────────── */}
      <div style={styles.field}>
        <label style={styles.label}>Product</label>
        <div style={styles.chipGroup}>
          {products.map((p) => {
            const active = selectedProduct === p;
            return (
              <button
                key={p}
                type="button"
                onClick={() => setSelectedProduct(p)}
                style={{ ...styles.chip, ...(active ? styles.chipActive : {}) }}
              >
                {p}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Test Process ───────────────────────────────────────── */}
      <div style={styles.field}>
        <label style={styles.label}>Test Process</label>
        <div style={styles.chipGroup}>
          {PROCESSES.map((p) => {
            const active = selectedProcesses.includes(p);
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

      {/* ── Buttons ────────────────────────────────────────────── */}
      <div style={styles.buttons}>
        <button
          style={{ ...styles.primaryBtn, ...(disabled ? styles.btnDisabled : {}) }}
          onClick={() => onGenerate(buildRequest())}
          disabled={disabled}
        >
          {loading ? "Loading…" : "Generate Report"}
        </button>
        <button
          style={{
            ...styles.secondaryBtn,
            ...(!canPrint || disabled ? styles.btnDisabled : {}),
          }}
          onClick={() => exportPdf(buildRequest())}
          disabled={!canPrint || disabled}
        >
          Export PDF
        </button>
      </div>

      <div style={styles.footer}>
        <span
          style={{
            ...styles.footerDot,
            background: isMock === false ? "var(--notion-blue)" : "var(--green)",
          }}
        />
        {isMock === null ? "Connecting…" : isMock ? "Mock data mode" : "Live DB mode"}
      </div>
    </aside>
  );
}

const styles: Record<string, React.CSSProperties> = {
  sidebar: {
    width: 280,
    minHeight: "100vh",
    background: "var(--white)",
    padding: "28px 22px",
    display: "flex",
    flexDirection: "column",
    gap: 24,
    borderRight: "var(--border-whisper)",
    flexShrink: 0,
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    paddingBottom: 12,
    borderBottom: "var(--border-soft)",
  },
  brandMark: {
    width: 32,
    height: 32,
    borderRadius: 8,
    background: "var(--notion-blue)",
    color: "var(--white)",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: 700,
    fontSize: 16,
    letterSpacing: "-0.02em",
  },
  brandLogo: {
    height: 32,
    width: "auto",
    maxWidth: 120,
    objectFit: "contain",
    display: "block",
  },
  brandTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--gray-700)",
    lineHeight: 1.2,
    letterSpacing: "-0.01em",
  },
  brandSub: {
    fontSize: 11,
    color: "var(--gray-400)",
    marginTop: 2,
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  label: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    color: "var(--gray-500)",
    fontSize: 11,
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
  chipGroup: {
    display: "flex",
    gap: 6,
    flexWrap: "wrap",
  },
  chip: {
    padding: "6px 14px",
    borderRadius: 999,
    border: "var(--border-whisper)",
    background: "var(--white)",
    color: "var(--gray-500)",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
    transition: "all 120ms ease",
  },
  chipActive: {
    background: "var(--badge-bg)",
    color: "var(--badge-text)",
    border: "1px solid rgba(9, 127, 232, 0.3)",
  },
  buttons: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    marginTop: "auto",
  },
  primaryBtn: {
    background: "var(--notion-blue)",
    color: "var(--white)",
    border: "none",
    borderRadius: 6,
    padding: "10px 0",
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
    boxShadow: "var(--shadow-button)",
    transition: "background 120ms ease",
  },
  secondaryBtn: {
    background: "var(--white)",
    color: "var(--gray-700)",
    border: "var(--border-whisper)",
    borderRadius: 6,
    padding: "10px 0",
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
  },
  btnDisabled: {
    opacity: 0.5,
    cursor: "not-allowed",
  },
  footer: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 11,
    color: "var(--gray-400)",
    paddingTop: 12,
    borderTop: "var(--border-soft)",
  },
  footerDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    display: "inline-block",
    transition: "background 300ms",
  },
};
