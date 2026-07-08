import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchProducts, fetchWaferMapLots, fetchWaferMaps } from "../api/client";
import type { Product, WaferMapLotsResponse, WaferMapResponse } from "../types";
import WaferMapGrid from "../components/wafermap/WaferMapGrid";
import BinLegend from "../components/wafermap/BinLegend";

const MAX_LOTS = 12;

// Okabe–Ito colorblind-safe categorical palette (fail bins, legend order).
const PALETTE = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#999999"];

const todayStr = () => new Date().toISOString().slice(0, 10);
const daysAgoStr = (days: number) => new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);

export default function WaferMapPage() {
  const [searchParams] = useSearchParams();

  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState(searchParams.get("product_id") ?? "");
  const [process, setProcess] = useState(searchParams.get("process") ?? "CP");
  const [startDate, setStartDate] = useState(searchParams.get("start") ?? daysAgoStr(90));
  const [endDate, setEndDate] = useState(searchParams.get("end") ?? todayStr());
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

  // Guards loadLots against out-of-order responses: only the latest request
  // may write state when product/process changes mid-fetch.
  const lotsReqIdRef = useRef(0);

  const loadLots = useCallback(async () => {
    if (!productId || !process) return;
    const id = ++lotsReqIdRef.current;
    setLotsLoading(true);
    setLotsError(null);
    try {
      const res = await fetchWaferMapLots(productId, process, startDate, endDate, sub || undefined);
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
  }, [productId, process, startDate, endDate, sub]);

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

  const displayLots = lotsData ? [...lotsData.lots].reverse() : []; // newest first

  return (
    <main style={styles.container}>
      <header style={styles.header}>
        <div style={styles.breadcrumb}>Analysis · Wafer Map</div>
        <h1 style={styles.title}>Wafer Map</h1>
      </header>

      <div style={styles.controls}>
        <label style={styles.field}>
          <span style={styles.fieldLabel}>Product</span>
          <select
            value={productId}
            onChange={(e) => { setProductId(e.target.value); setSub(""); }}
            style={styles.select}
          >
            {products.map((p) => (
              <option key={p.product_id} value={p.product_id}>
                {p.product_id}{p.display_name && p.display_name !== p.product_id ? ` — ${p.display_name}` : ""}
              </option>
            ))}
          </select>
        </label>

        <label style={styles.field}>
          <span style={styles.fieldLabel}>Process</span>
          <select
            value={process}
            onChange={(e) => { setProcess(e.target.value); setSub(""); }}
            style={styles.select}
          >
            <option value="CP">CP</option>
            <option value="FT">FT</option>
            <option value="SLT">SLT</option>
          </select>
        </label>

        <label style={styles.field}>
          <span style={styles.fieldLabel}>From</span>
          <input
            type="date"
            value={startDate}
            max={endDate}
            onChange={(e) => setStartDate(e.target.value)}
            style={styles.select}
          />
        </label>

        <label style={styles.field}>
          <span style={styles.fieldLabel}>To</span>
          <input
            type="date"
            value={endDate}
            min={startDate}
            onChange={(e) => setEndDate(e.target.value)}
            style={styles.select}
          />
        </label>

        <button onClick={() => loadLots()} disabled={lotsLoading} style={styles.refresh}>
          {lotsLoading ? "Loading…" : "🔄 Load lots"}
        </button>
      </div>

      {lotsError && <div style={styles.error}>{lotsError}</div>}

      <div style={styles.row}>
        <div style={{ ...styles.card, ...styles.halfCard }}>
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
          {lotsLoading && <p style={styles.empty}>Loading lots…</p>}
          {!lotsLoading && lotsData && lotsData.lots.length === 0 && (
            <p style={styles.empty}>No lots found.</p>
          )}
          {!lotsLoading && displayLots.length > 0 && (
            <div style={styles.lotList}>
              {displayLots.map((l) => {
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
          )}
          <button
            onClick={() => handleShowMaps()}
            disabled={selectedLots.length === 0 || mapLoading}
            style={{
              ...styles.primaryBtn,
              ...(selectedLots.length === 0 || mapLoading ? styles.btnDisabled : {}),
            }}
          >
            {mapLoading ? "Loading…" : "Show maps"}
          </button>
        </div>

        <div style={{ ...styles.card, ...styles.halfCard }}>
          <div style={styles.lotsHeader}>
            <span style={styles.lotsTitle}>Bin filter</span>
            {mapData && <span style={styles.lotsCounter}>{mapData.legend.length}</span>}
          </div>
          <div style={styles.binScroll}>
            {mapData && mapData.legend.length > 0 ? (
              <BinLegend
                legend={mapData.legend}
                colorFor={colorFor}
                selectedBins={selectedBins}
                onToggle={toggleBin}
              />
            ) : (
              <p style={styles.empty}>Show maps to list bins.</p>
            )}
          </div>
        </div>
      </div>

      {mapError && <div style={styles.error}>{mapError}</div>}

      {mapData && (
        <div style={styles.card}>
          <div style={styles.mapMeta}>
            {mapData.wafers.length} wafers loaded for {mapData.display_name} / {mapData.process}
          </div>
          <div style={styles.gridSpacer}>
            <WaferMapGrid
              wafers={mapData.wafers}
              colorFor={colorFor}
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
  controls: { display: "flex", alignItems: "center", gap: 18, marginBottom: 20, flexWrap: "wrap" },
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
  row: { display: "flex", gap: 16, alignItems: "flex-start" },
  halfCard: { flex: 1, minWidth: 0, width: "50%", marginBottom: 0 },
  binScroll: {
    height: 180,
    overflowY: "auto",
    marginTop: 12,
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
  lotList: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    maxHeight: 180,
    overflowY: "auto",
    marginBottom: 16,
    border: "var(--border-whisper)",
    borderRadius: 8,
    padding: 6,
  },
  lotItem: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 13,
    color: "var(--gray-700)",
    padding: "6px 8px",
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
