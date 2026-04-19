import axios from "axios";
import type { YieldRequest, YieldResponse } from "../types";

const api = axios.create({
  baseURL: "http://localhost:8000/api",
});

export async function fetchProducts(): Promise<string[]> {
  const res = await api.get<string[]>("/products");
  return res.data;
}

export async function fetchYieldData(
  req: YieldRequest
): Promise<YieldResponse> {
  const res = await api.post<YieldResponse>("/yield-data", req);
  return res.data;
}

export async function exportPdf(req: YieldRequest): Promise<void> {
  const res = await api.post("/export-pdf", req, { responseType: "blob" });
  const blob = new Blob([res.data], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `YieldTrend_${req.product}_${req.start_month}_to_${req.end_month}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}
