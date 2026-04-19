export interface YieldRequest {
  product: string;
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
  data: Record<string, ProcessData>;
}
