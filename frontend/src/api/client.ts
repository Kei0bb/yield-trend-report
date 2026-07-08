import axios from "axios";
import type {
  Product, YieldRequest, YieldResponse,
  DashboardSummaryResponse, ExploreLotsResponse,
  WaferMapLotsResponse, WaferMapResponse,
} from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api",
});

export async function fetchProducts(): Promise<Product[]> {
  const res = await api.get<Product[]>("/products");
  return res.data;
}

export async function fetchReportProducts(): Promise<Product[]> {
  const res = await api.get<Product[]>("/report-products");
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
  months = 6, process = "all", force = false
): Promise<DashboardSummaryResponse> {
  const res = await api.get<DashboardSummaryResponse>("/dashboard/summary", {
    params: { months, process, force },
  });
  return res.data;
}

export async function fetchExploreLots(
  productId: string, process: string, months = 6, sub?: string
): Promise<ExploreLotsResponse> {
  const res = await api.get<ExploreLotsResponse>("/explore/lots", {
    params: { product_id: productId, process, months, ...(sub ? { sub } : {}) },
  });
  return res.data;
}

export async function fetchProcessUnits(
  productId: string
): Promise<{ family: string; label: string }[]> {
  const res = await api.get<{ family: string; label: string }[]>("/process-units", {
    params: { product_id: productId },
  });
  return res.data;
}

export async function fetchWaferMapLots(
  productId: string, process: string, start: string, end: string, sub?: string
): Promise<WaferMapLotsResponse> {
  const res = await api.get<WaferMapLotsResponse>("/wafermap/lots", {
    params: { product_id: productId, process, start, end, ...(sub ? { sub } : {}) },
  });
  return res.data;
}

export async function fetchWaferMaps(req: {
  product_id: string;
  process: string;
  lot_ids: string[];
  months?: number;
  sub?: string;
}): Promise<WaferMapResponse> {
  const res = await api.post<WaferMapResponse>("/wafermap", req);
  return res.data;
}

