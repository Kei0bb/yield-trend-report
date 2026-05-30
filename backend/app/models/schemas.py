from pydantic import BaseModel


class YieldRequest(BaseModel):
    products: list[str]    # 比較したい品種リスト（1 品種以上）
    start_month: str       # "YYYY-MM"
    end_month: str         # "YYYY-MM"
    processes: list[str]   # ["CP", "FT", "SLT"]


class ProcessData(BaseModel):
    lots: list[str]
    yield_avg: list[float | None]  # None = no data for that week
    fail_bins: dict[str, list[float]]  # bin_name -> per-lot bin%


class YieldResponse(BaseModel):
    # process -> product -> ProcessData
    # 例: data["CP"]["PRODUCT-A"] = ProcessData(...)
    data: dict[str, dict[str, ProcessData]]


# ---------------------------------------------------------------------------
# Dashboard / Explore models (additive — existing models above are unchanged)
# ---------------------------------------------------------------------------


class Warning(BaseModel):
    type: str                      # "yield_drop" | "bin_surge"
    message: str
    severity: str = "warn"
    bin_code: int | None = None


class BinBreakdown(BaseModel):
    bin_name: str
    bin_codes: list[int]
    count: int
    percent: float


class LotData(BaseModel):
    lot_id: str
    lot_date: str                  # ISO "YYYY-MM-DD"
    wafer_count: int
    yield_pct: float
    bin_breakdown: list[BinBreakdown] = []
    warnings: list[Warning] = []


class ExploreLotsResponse(BaseModel):
    nickname: str
    process: str
    period: dict
    lots: list[LotData]
    available_bins: list[str]


class SparkPoint(BaseModel):
    lot_id: str
    lot_date: str
    yield_pct: float


class SummaryRow(BaseModel):
    nickname: str
    display_name: str
    process: str
    latest_yield: float | None
    latest_lot_id: str | None
    latest_lot_date: str | None
    avg_yield_6m: float | None
    delta: float | None
    sparkline: list[SparkPoint] = []
    warnings: list[Warning] = []


class DashboardSummaryResponse(BaseModel):
    generated_at: str
    period: dict
    rows: list[SummaryRow]
