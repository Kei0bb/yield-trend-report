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
  latest_yield: number | null;
  latest_lot_id: string | null;
  latest_lot_date: string | null;
  avg_yield_6m: number | null;
  delta: number | null;
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
}

export interface ExploreLotsResponse {
  product_id: string;
  display_name: string;
  process: string;
  period: { months: number; start: string; end: string };
  lots: LotData[];
  available_bins: string[];
}
