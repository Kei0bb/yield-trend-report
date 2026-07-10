import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchProcessSubs, fetchProducts, fetchWaferMapLots, fetchWaferMaps } from "../api/client";
import type { Product, WaferMapLotsResponse, WaferMapResponse } from "../types";
import WaferMapGrid from "../components/wafermap/WaferMapGrid";
import BinLegend from "../components/wafermap/BinLegend";
import FilterCard from "../components/wafermap/FilterCard";
import { copyGridToClipboard } from "../components/wafermap/copyGrid";

const MAX_LOTS = 12;

// Okabe–Ito colorblind-safe categorical palette (fail bins, legend order).
const PALETTE = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#999999"];

const todayStr = () => new Date().toISOString().slice(0, 10);
const monthsAgoStr = (m: number) => { const d = new Date(); d.setMonth(d.getMonth() - m); return d.toISOString().slice(0, 10); };

export default function WaferMapPage() {
  const [searchParams] = useSearchParams();

  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState(searchParams.get("product_id") ?? "");
  const [process, setProcess] = useState(searchParams.get("process") ?? "CP");
  const [months, setMonths] = useState(() => {
    const m = parseInt(searchParams.get("months") ?? "", 10);
    return [1, 3, 6].includes(m) ? m : 3;
  });
  const [sub, setSub] = useState(searchParams.get("sub") ?? "");

  const [lotsData, setLotsData] = useState<WaferMapLotsResponse | null>(null);
  const [lotsLoading, setLotsLoading] = useState(false);
  const [lotsError, setLotsError] = useState<string | null>(null);

  const [selectedLots, setSelectedLots] = useState<string[]>(() => {
    const l = searchParams.get("lots");
    return l ? l.split(",").filter(Boolean).slice(0, MAX_LOTS) : [];
  });

  const [mapData, setMapData] = useState<WaferMapResponse | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [selectedBins, setSelectedBins] = useState<number[]>([]);

  const [subsByProcess, setSubsByProcess] = useState<Record<string, string[]>>({});
  const [copyMsg, setCopyMsg] = useState<string>("");
  const gridRef = useRef<HTMLDivElement>(null);

  // Load the product list once; default to the first product if none was
  // supplied via the URL (Explore deep-link).
  useEffect(() => {
    fetchProducts()
      .then((list) => {
        setProducts(list);
        setProductId((prev) => prev || (list.length > 0 ? list[0].product_id : prev));
      })
      .catch((e) => {
        console.error("Failed to load products:", e);
        setLotsError("Failed to load products.");
      });
  }, []);

  // Fetch sub-process options whenever the selected product changes.
  useEffect(() => {
    if (!productId) {
      setSubsByProcess({});
      return;
    }
    fetchProcessSubs(productId)
      .then(setSubsByProcess)
      .catch(() => setSubsByProcess({}));
  }, [productId]);

  // Guards loadLots against out-of-order responses: only the latest request
  // may write state when product/process changes mid-fetch.
  const lotsReqIdRef = useRef(0);

  const loadLots = useCallback(async () => {
    if (!productId || !process) return;
    const id = ++lotsReqIdRef.current;
    setLotsLoading(true);
    setLotsError(null);
    try {
      const res = await fetchWaferMapLots(productId, process, monthsAgoStr(months), todayStr(), sub || undefined);
      if (id !== lotsReqIdRef.current) return; // stale response
      setLotsData(res);
    } catch (e) {
      if (id !== lotsReqIdRef.current) return; // stale response
      console.error("Failed to load lots:", e);
      setLotsError("Failed to load lots.");
      setLotsData(null);
    } finally {
      if (id === lotsReqIdRef.current) setLotsLoading(false);
    }
  }, [productId, process, months, sub]);

  const handleShowMaps = useCallback(async (lotIds?: string[]) => {
    const ids = lotIds ?? selectedLots;
    if (ids.length === 0 || !productId || !process) return;
    setMapLoading(true);
    setMapError(null);
    try {
      const res = await fetchWaferMaps({
        product_id: productId, process, lot_ids: ids, sub: sub || undefined,
      });
      setMapData(res);
      setSelectedBins([]);
    } catch (e) {
      console.error("Failed to load wafer maps:", e);
      setMapError("Failed to load wafer maps.");
      setMapData(null);
    } finally {
      setMapLoading(false);
    }
  }, [selectedLots, productId, process, sub]);

  const colorFor = useCallback(
    (bin: number) => {
      const legend = mapData?.legend ?? [];
      const i = legend.findIndex((l) => l.bin_code === bin);
      return i >= 0 && i < PALETTE.length ? PALETTE[i] : "#999999"; // beyond top-8 → gray
    },
    [mapData],
  );

  // Explore deep-link entry: if product_id + process + lots were supplied on
  // the URL, auto-fetch the maps once on mount.
  const autoFetchedRef = useRef(false);
  useEffect(() => {
    if (autoFetchedRef.current) return;
    autoFetchedRef.current = true;
    const spProduct = searchParams.get("product_id");
    const spProcess = searchParams.get("process");
    const spLots = searchParams.get("lots");
    if (spProduct && spProcess && spLots) {
      const lotIds = spLots.split(",").filter(Boolean).slice(0, MAX_LOTS);
      if (lotIds.length > 0) void handleShowMaps(lotIds);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleLot = (lotId: string) => {
    setSelectedLots((prev) => {
      if (prev.includes(lotId)) return prev.filter((x) => x !== lotId);
      if (prev.length >= MAX_LOTS) return prev;
      return [...prev, lotId];
    });
  };

  const toggleBin = (b: number) => {
    setSelectedBins((prev) => (prev.includes(b) ? prev.filter((x) => x !== b) : [...prev, b]));
  };

  const handleCopy = async () => {
    if (!gridRef.current) return;
    try {
      await copyGridToClipboard(gridRef.current);
      setCopyMsg("Copied!");
    } catch (e) {
      console.error(e);
      setCopyMsg("Copy failed");
    }
    setTimeout(() => setCopyMsg(""), 2000); // note: acceptable here (not a workflow script)
  };

  const displayLots = lotsData ? [...lotsData.lots].reverse() : []; // newest first

  return (
    <main style={styles.container}>
      <header style={styles.header}>
        <div style={styles.breadcrumb}>Analysis · Wafer Map</div>
        <h1 style={styles.title}>Wafer Map</h1>
      </header>

      {lotsError && <div style={styles.error}>{lotsError}</div>}

      <div style={styles.row}>
        <FilterCard
          title="Product" grow={2} minWidth={170} value={productId}
          onChange={(v) => { setProductId(v); setSub(""); }}
          options={products.map((p) => ({ value: p.product_id, label: p.product_id + (p.display_name && p.display_name !== p.product_id ? ` — ${p.display_name}` : "") }))}
        />
        <FilterCard
          title="Process" grow={1} minWidth={90} value={process}
          onChange={(v) => { setProcess(v); setSub(""); }}
          options={[{ value: "CP", label: "CP" }, { value: "FT", label: "FT" }, { value: "SLT", label: "SLT" }]}
        />
        <FilterCard
          title="Sub" grow={1} minWidth={100} value={sub}
          onChange={setSub}
          options={[{ value: "", label: "All" }, ...(subsByProcess[process] || []).map((s) => ({ value: s, label: s }))]}
        />
        <FilterCard
          title="Period" grow={1.5} minWidth={130} value={String(months)}
          onChange={(v) => setMonths(Number(v))}
          options={[{ value: "1", label: "Last 1 month" }, { value: "3", label: "Last 3 months" }, { value: "6", label: "Last 6 months" }]}
          footer={
            <button onClick={() => loadLots()} disabled={lotsLoading} style={{ ...styles.refresh, width: "100%", marginTop: 12 }}>
              {lotsLoading ? "Loading…" : "🔄 Load lots"}
            </button>
          }
        />

        <div style={{ ...styles.card, ...styles.filterCard, flex: "2 1 0", minWidth: 200 }}>
          <div style={styles.lotsHeader}>
            <span style={styles.lotsTitle}>Lots</span>
            <div style={styles.lotsHeaderActions}>
              <button type="button" style={styles.linkBtn} onClick={() => setSelectedLots(displayLots.slice(0, MAX_LOTS).map((l) => l.lot_id))}>
                Select all
              </button>
              <button type="button" style={styles.linkBtn} onClick={() => setSelectedLots([])}>
                Clear
              </button>
              <span style={styles.lotsCounter}>{selectedLots.length}/{MAX_LOTS}</span>
            </div>
          </div>
          <div style={styles.scrollBox}>
            {lotsLoading && <p style={styles.empty}>Loading lots…</p>}
            {!lotsLoading && lotsData && lotsData.lots.length === 0 && (
              <p style={styles.empty}>No lots found.</p>
            )}
            {!lotsLoading && displayLots.map((l) => {
              const checked = selectedLots.includes(l.lot_id);
              const disabled = !checked && selectedLots.length >= MAX_LOTS;
              return (
                <label
                  key={l.lot_id}
                  style={{ ...styles.lotItem, ...(disabled ? styles.lotItemDisabled : {}) }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={disabled}
                    onChange={() => toggleLot(l.lot_id)}
                  />
                  <span>{l.lot_id}</span>
                </label>
              );
            })}
          </div>
          <button
            onClick={() => handleShowMaps()}
            disabled={selectedLots.length === 0 || mapLoading}
            style={{
              ...styles.primaryBtn,
              alignSelf: "flex-start",
              marginTop: 12,
              ...(selectedLots.length === 0 || mapLoading ? styles.btnDisabled : {}),
            }}
          >
            {mapLoading ? "Loading…" : "Show maps"}
          </button>
        </div>

        <div style={{ ...styles.card, ...styles.filterCard, flex: "1.5 1 0", minWidth: 160 }}>
          <div style={styles.lotsHeader}>
            <span style={styles.lotsTitle}>Bin filter</span>
            {mapData && <span style={styles.lotsCounter}>{mapData.legend.length}</span>}
          </div>
          <div style={styles.scrollBox}>
            {mapData && mapData.legend.length > 0 && (
              <BinLegend
                legend={mapData.legend}
                colorFor={colorFor}
                selectedBins={selectedBins}
                onToggle={toggleBin}
              />
            )}
          </div>
        </div>
      </div>

      {mapError && <div style={styles.error}>{mapError}</div>}

      {mapData && (
        <div style={styles.card}>
          <div style={styles.mapHeaderRow}>
            <div style={styles.mapMeta}>
              {mapData.wafers.length} wafers loaded for {mapData.display_name} / {mapData.process}
            </div>
            <div style={styles.copyRow}>
              {copyMsg && <span style={styles.copyMsg}>{copyMsg}</span>}
              <button onClick={handleCopy} style={styles.refresh}>
                📋 Copy image
              </button>
            </div>
          </div>
          <div style={styles.gridSpacer}>
            <WaferMapGrid
              wafers={mapData.wafers}
              colorFor={colorFor}
              containerRef={gridRef}
              passBinCodes={mapData.pass_bin_codes}
              selectedBins={selectedBins}
            />
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
  mapHeaderRow: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  copyRow: { display: "flex", alignItems: "center", gap: 10 },
  copyMsg: { fontSize: 12, color: "var(--gray-400)" },
  refresh: {
    padding: "7px 16px",
    cursor: "pointer",
    borderRadius: 8,
    border: "var(--border-whisper)",
    background: "var(--white)",
    color: "var(--gray-700)",
    fontSize: 13,
    fontWeight: 500,
    boxShadow: "var(--shadow-button)",
  },
  error: {
    background: "rgba(224, 62, 62, 0.08)",
    color: "var(--red)",
    padding: "10px 14px",
    borderRadius: 8,
    marginBottom: 16,
    fontSize: 13,
  },
  card: {
    background: "var(--white)",
    border: "var(--border-whisper)",
    borderRadius: 12,
    boxShadow: "var(--shadow-card)",
    padding: 20,
    marginBottom: 20,
  },
  row: { display: "flex", gap: 16, alignItems: "flex-start", marginBottom: 20, flexWrap: "wrap" },
  filterCard: {
    flex: "0 0 auto",
    marginBottom: 0,
    height: 340,
    display: "flex",
    flexDirection: "column",
  },
  scrollBox: {
    flex: 1,
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    gap: 4,
    overflowY: "auto",
    border: "var(--border-whisper)",
    borderRadius: 8,
    padding: 6,
  },
  lotsHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  lotsHeaderActions: { display: "flex", alignItems: "center", gap: 10 },
  lotsTitle: { fontSize: 14, fontWeight: 600, color: "var(--gray-700)" },
  lotsCounter: { fontSize: 12, color: "var(--gray-400)", fontVariantNumeric: "tabular-nums" },
  linkBtn: {
    background: "none",
    border: "none",
    padding: 0,
    color: "var(--notion-blue)",
    fontSize: 12,
    fontWeight: 500,
    cursor: "pointer",
  },
  lotItem: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    fontWeight: 500,
    color: "var(--gray-700)",
    padding: "4px 8px",
    borderRadius: 6,
    cursor: "pointer",
  },
  lotItemDisabled: { color: "var(--gray-400)", cursor: "not-allowed" },
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
  btnDisabled: { opacity: 0.5, cursor: "not-allowed" },
  mapMeta: { color: "var(--gray-400)", fontSize: 13, marginBottom: 12 },
  gridSpacer: { marginTop: 16 },
  empty: { color: "var(--gray-400)", fontSize: 14 },
};
