import axios from "axios";
import type { YieldRequest, YieldResponse } from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api",
});

export async function fetchProducts(): Promise<string[]> {
  const res = await api.get<string[]>("/products");
  return res.data;
}

export async function fetchYieldData(req: YieldRequest): Promise<YieldResponse> {
  const res = await api.post<YieldResponse>("/yield-data", req);
  return res.data;
}

export async function fetchHealth(): Promise<{ status: string; mock: boolean }> {
  const res = await api.get<{ status: string; mock: boolean }>("/health", {
    baseURL: import.meta.env.VITE_API_BASE_URL?.replace("/api", "") ?? "http://localhost:8000",
  });
  return res.data;
}
