import axios from "axios";
import type {
  YieldRequest, YieldResponse,
  DashboardSummaryResponse, ExploreLotsResponse,
} from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api",
});

export async function fetchProducts(): Promise<string[]> {
  const res = await api.get<string[]>("/products");
  return res.data;
}

export async function fetchYieldData(req: YieldRequest): Promise<YieldResponse> {
  const res = await api.post<YieldResponse>("/yield-data", req);
  return res.data;
}

export async function exportPdf(req: YieldRequest): Promise<void> {
  const res = await api.post("/export-pdf", req, { responseType: "blob" });
  const blob = new Blob([res.data], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const productsLabel = req.products.join("_vs_");
  a.download = `YieldTrend_${productsLabel}_${req.start_month}_to_${req.end_month}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function fetchHealth(): Promise<{ status: string; mock: boolean }> {
  const res = await api.get<{ status: string; mock: boolean }>("/health", {
    baseURL: import.meta.env.VITE_API_BASE_URL?.replace("/api", "") ?? "",
  });
  return res.data;
}

export async function fetchDashboardSummary(
  months = 6, process = "all"
): Promise<DashboardSummaryResponse> {
  const res = await api.get<DashboardSummaryResponse>("/dashboard/summary", {
    params: { months, process },
  });
  return res.data;
}

export async function fetchExploreLots(
  nickname: string, process: string, months = 6
): Promise<ExploreLotsResponse> {
  const res = await api.get<ExploreLotsResponse>("/explore/lots", {
    params: { nickname, process, months },
  });
  return res.data;
}

export async function fetchAnomalyConfig(): Promise<Record<string, unknown>> {
  const res = await api.get<Record<string, unknown>>("/anomaly/config");
  return res.data;
}
