from pydantic import BaseModel, Field


class YieldRequest(BaseModel):
    products: list[str]    # list of product_ids (single-product in UI)
    start_month: str       # "YYYY-MM"
    end_month: str         # "YYYY-MM"
    processes: list[str]   # ["CP", "FT", "SLT"]


class ProcessData(BaseModel):
    lots: list[str]
    yield_avg: list[float | None]  # None = no data for that week
    fail_bins: dict[str, list[float]]  # bin_name -> per-lot bin%


class YieldResponse(BaseModel):
    # process -> display_name -> ProcessData
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
    test_program_rev: str = ""


class ExploreLotsResponse(BaseModel):
    product_id: str
    display_name: str
    process: str
    period: dict
    lots: list[LotData]
    available_bins: list[str]
    target: float | None = None


class SparkPoint(BaseModel):
    lot_id: str
    lot_date: str
    yield_pct: float


class SummaryRow(BaseModel):
    nickname: str
    product_id: str
    display_name: str
    process: str
    process_label: str = ""    # display label: major name (level 0) or DB PROCESS value (level 1)
    level: int = 0             # 0 = major row, 1 = sub-process row
    latest_yield: float | None
    latest_lot_id: str | None
    latest_lot_date: str | None
    avg_yield_6m: float | None
    delta: float | None
    target: float | None = None
    sparkline: list[SparkPoint] = []
    warnings: list[Warning] = []


class DashboardSummaryResponse(BaseModel):
    generated_at: str
    period: dict
    rows: list[SummaryRow]


# ---------------------------------------------------------------------------
# Wafer Map models (additive — existing models above are unchanged)
# ---------------------------------------------------------------------------


class WaferMapWafer(BaseModel):
    lot_id: str
    wafer_id: str
    # Parallel arrays, one entry per die; `bin` holds raw DB bin codes.
    x: list[int]
    y: list[int]
    bin: list[int]


class WaferMapLegendItem(BaseModel):
    bin_code: int
    label: str
    count: int


class WaferMapLotInfo(BaseModel):
    lot_id: str
    lot_date: str
    wafer_count: int
    test_program_rev: str = ""


class WaferMapLotsResponse(BaseModel):
    product_id: str
    process: str
    lots: list[WaferMapLotInfo]


class WaferMapRequest(BaseModel):
    product_id: str
    process: str
    lot_ids: list[str] = Field(..., min_length=1, max_length=12)
    months: int = 6
    sub: str | None = None


class WaferMapResponse(BaseModel):
    product_id: str
    display_name: str
    process: str
    wafers: list[WaferMapWafer]
    legend: list[WaferMapLegendItem]
    pass_bin_codes: list[int]
