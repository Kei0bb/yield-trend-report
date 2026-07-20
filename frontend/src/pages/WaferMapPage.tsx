import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchProcessSubs, fetchProducts, fetchWaferMapLots, fetchWaferMaps } from "../api/client";
import type { Product, WaferMapLotsResponse, WaferMapResponse } from "../types";
import WaferMapGrid from "../components/wafermap/WaferMapGrid";
import { copyGridToClipboard } from "../components/wafermap/copyGrid";
import CheckListCard from "../ui/CheckListCard";
import Button from "../ui/Button";
import PageTitle from "../ui/PageTitle";

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
      <PageTitle breadcrumb="Analysis · Wafer Map" title="Wafer Map" />

      {lotsError && <div style={styles.error}>{lotsError}</div>}

      <div style={styles.row}>
        <CheckListCard
          title="Product" grow={1.65} minWidth={140}
          selected={[productId]}
          onToggle={(v) => { setProductId(v); setSub(""); }}
          options={products.map((p) => ({ value: p.product_id, label: p.product_id + (p.display_name && p.display_name !== p.product_id ? ` — ${p.display_name}` : "") }))}
        />
        <CheckListCard
          title="Process" grow={1} minWidth={90}
          selected={[process]}
          onToggle={(v) => { setProcess(v); setSub(""); }}
          options={[{ value: "CP", label: "CP" }, { value: "FT", label: "FT" }, { value: "SLT", label: "SLT" }]}
        />
        <CheckListCard
          title="Sub" grow={1} minWidth={100}
          selected={[sub]}
          onToggle={setSub}
          options={[{ value: "", label: "All" }, ...(subsByProcess[process] || []).map((s) => ({ value: s, label: s }))]}
        />
        <CheckListCard
          title="Period" grow={1.5} minWidth={130}
          selected={[String(months)]}
          onToggle={(v) => setMonths(Number(v))}
          options={[{ value: "1", label: "Last 1 month" }, { value: "3", label: "Last 3 months" }, { value: "6", label: "Last 6 months" }]}
          footer={
            <Button onClick={() => loadLots()} disabled={lotsLoading} style={{ width: "100%", marginTop: 12 }}>
              {lotsLoading ? "Loading…" : "🔄 Load lots"}
            </Button>
          }
        />
        <CheckListCard
          title="Lots" grow={1.85} minWidth={200}
          selected={selectedLots}
          onToggle={toggleLot}
          options={lotsLoading ? [] : displayLots.map((l) => ({
            value: l.lot_id,
            label: l.lot_id,
            disabled: !selectedLots.includes(l.lot_id) && selectedLots.length >= MAX_LOTS,
          }))}
          emptyText={lotsLoading ? "Loading lots…" : lotsData ? "No lots found." : undefined}
          headerRight={
            <>
              <Button variant="ghost" onClick={() => setSelectedLots(displayLots.slice(0, MAX_LOTS).map((l) => l.lot_id))}>Select all</Button>
              <Button variant="ghost" onClick={() => setSelectedLots([])}>Clear</Button>
              <span style={styles.lotsCounter}>{selectedLots.length}/{MAX_LOTS}</span>
            </>
          }
          footer={
            <Button
              variant="primary"
              onClick={() => handleShowMaps()}
              disabled={selectedLots.length === 0 || mapLoading}
              style={{ alignSelf: "flex-start", marginTop: 12 }}
            >
              {mapLoading ? "Loading…" : "Show maps"}
            </Button>
          }
        />
        <CheckListCard
          title="Bin filter" grow={1.65} minWidth={190}
          selected={selectedBins.map(String)}
          onToggle={(v) => toggleBin(Number(v))}
          options={(mapData?.legend ?? []).map((item) => ({
            value: String(item.bin_code),
            label: `${item.label} (${item.count})`,
            swatch: colorFor(item.bin_code),
          }))}
          headerRight={mapData ? <span style={styles.lotsCounter}>{mapData.legend.length}</span> : undefined}
        />
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
              <Button onClick={handleCopy}>📋 Copy image</Button>
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
    background: "var(--canvas)",
    minWidth: 0,
  },
  mapHeaderRow: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  copyRow: { display: "flex", alignItems: "center", gap: 10 },
  copyMsg: { fontSize: 12, color: "var(--muted-soft)" },
  error: {
    background: "rgba(198, 69, 69, 0.08)",
    color: "var(--error)",
    padding: "10px 14px",
    borderRadius: "var(--radius-control)",
    marginBottom: 16,
    fontSize: 13,
  },
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: 20,
    marginBottom: 20,
  },
  row: { display: "flex", gap: 16, alignItems: "flex-start", marginBottom: 20, flexWrap: "wrap" },
  lotsCounter: { fontSize: 12, color: "var(--muted-soft)", fontVariantNumeric: "tabular-nums" },
  mapMeta: { color: "var(--muted-soft)", fontSize: 13 },
  gridSpacer: { marginTop: 16 },
};
