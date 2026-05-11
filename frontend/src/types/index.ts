export interface YieldRequest {
  products: string[];   // 比較品種リスト（1 品種以上）
  start_month: string;
  end_month: string;
  processes: string[];
}

export interface ProcessData {
  lots: string[];
  yield_avg: number[];
  fail_bins: Record<string, number[]>;
}

export interface YieldResponse {
  // data[process][product] = ProcessData
  data: Record<string, Record<string, ProcessData>>;
}
