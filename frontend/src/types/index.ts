export interface Product {
  product_id: string;     // DB PRODUCT_ID (primary key shown/selected in the UI)
  display_name: string;   // product name (secondary label)
}

export interface YieldRequest {
  products: string[];   // target product_id (single select; kept as an array for API compatibility)
  start_month: string;
  end_month: string;
  processes: string[];
}

export interface ProcessData {
  lots: string[];
  yield_avg: (number | null)[];
  fail_bins: Record<string, number[]>;
}

export interface YieldResponse {
  // data[process][product] = ProcessData
  data: Record<string, Record<string, ProcessData>>;
}

// ---- Dashboard / Explore types ----

export interface Warning {
  type: string;            // "yield_drop" | "bin_surge"
  message: string;
  severity: string;
  bin_code?: number | null;
}

export interface SparkPoint {
  lot_id: string;
  lot_date: string;
  yield_pct: number;
}

export interface SummaryRow {
  nickname: string;
  product_id: string;
  display_name: string;
  process: string;
  process_label: string;
  level: number;
  latest_yield: number | null;
  latest_lot_id: string | null;
  latest_lot_date: string | null;
  avg_yield_6m: number | null;
  delta: number | null;
  target?: number | null;
  sparkline: SparkPoint[];
  warnings: Warning[];
}

export interface DashboardSummaryResponse {
  generated_at: string;
  period: { months: number; start: string; end: string };
  rows: SummaryRow[];
}

export interface BinBreakdown {
  bin_name: string;
  bin_codes: number[];
  count: number;
  percent: number;
}

export interface LotData {
  lot_id: string;
  lot_date: string;
  wafer_count: number;
  yield_pct: number;
  bin_breakdown: BinBreakdown[];
  warnings: Warning[];
  test_program_rev: string;
}

export interface ExploreLotsResponse {
  product_id: string;
  display_name: string;
  process: string;
  period: { months: number; start: string; end: string };
  lots: LotData[];
  available_bins: string[];
  target?: number | null;
}

// ---- Wafer Map types ----

export interface WaferMapWafer {
  lot_id: string;
  wafer_id: string;
  // Parallel arrays, one entry per die; `bin` holds raw DB bin codes.
  x: number[];
  y: number[];
  bin: number[];
}

export interface WaferMapLegendItem {
  bin_code: number;
  label: string;
  count: number;
}

export interface WaferMapLotInfo {
  lot_id: string;
  lot_date: string;
  wafer_count: number;
  test_program_rev: string;
}

export interface WaferMapLotsResponse {
  product_id: string;
  process: string;
  lots: WaferMapLotInfo[];
}

export interface WaferMapResponse {
  product_id: string;
  display_name: string;
  process: string;
  wafers: WaferMapWafer[];
  legend: WaferMapLegendItem[];
  pass_bin_codes: number[];
}

// ---- PCM / WAT types ----

export interface WatLotInfo {
  lot_id: string;
  last_measured: string;
  wafer_count: number;
}

export interface WatLotsResponse {
  product_id: string;
  lots: WatLotInfo[];
}

export interface WatWaferPoint {
  wafer_id: number;
  n: number;
  mean: number | null;
  sigma: number | null;
}

export type WatStatus = "red" | "yellow" | "gray" | "ok";
export type WatCpkState = "value" | "infinite" | "undefined";

export interface WatItemStats {
  item_name: string;
  unit: string;
  spec_low: number | null;
  spec_high: number | null;
  n: number;
  mean: number | null;
  sigma: number | null;
  min: number | null;
  max: number | null;
  cpk: number | null;
  cpk_state: WatCpkState;
  oos_count: number;
  oos_pct: number;
  status: WatStatus;
  wafer_series: WatWaferPoint[];
}

export interface WatScatterPoint {
  wafer_id: number;
  site_no: number;
  x: number;
  y: number;
}

export interface WatScatterPlot {
  kind: "vth_np" | "idsat_np" | "ion_vt_n" | "ion_vt_p";
  x_item: string;
  y_item: string;
  x_unit: string;
  y_unit: string;
  x_spec: (number | null)[];
  y_spec: (number | null)[];
  points: WatScatterPoint[];
}

export interface WatScatterPair {
  label: string;
  plots: WatScatterPlot[];
}

export interface WatSummaryResponse {
  product_id: string;
  display_name: string;
  lot_id: string;
  measured_date: string;
  wafer_count: number;
  items: WatItemStats[];
  scatter_pairs: WatScatterPair[];
}
