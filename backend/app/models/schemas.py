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
    type: str                      # "bin_surge"
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
    months: int = Field(6, ge=1, le=6)
    sub: str | None = None


class WaferMapResponse(BaseModel):
    product_id: str
    display_name: str
    process: str
    wafers: list[WaferMapWafer]
    legend: list[WaferMapLegendItem]
    pass_bin_codes: list[int]


# ---------------------------------------------------------------------------
# PCM/WAT models (additive — existing models above are unchanged)
# ---------------------------------------------------------------------------


class WatLotInfo(BaseModel):
    lot_id: str
    last_measured: str
    wafer_count: int


class WatLotsResponse(BaseModel):
    product_id: str
    lots: list[WatLotInfo]


class WatWaferPoint(BaseModel):
    wafer_id: int
    n: int
    mean: float | None = None
    sigma: float | None = None


class WatItemStats(BaseModel):
    item_name: str
    unit: str = ""
    spec_low: float | None = None
    spec_high: float | None = None
    n: int
    mean: float | None = None
    sigma: float | None = None
    min: float | None = None
    max: float | None = None
    cpk: float | None = None
    cpk_state: str          # "value" | "infinite" | "undefined"
    oos_count: int
    oos_pct: float
    status: str             # "red" | "yellow" | "gray" | "ok"
    wafer_series: list[WatWaferPoint]


class WatScatterPoint(BaseModel):
    wafer_id: int
    site_no: int
    x: float
    y: float


class WatScatterPlot(BaseModel):
    kind: str               # vth_np | idsat_np | ion_vt_n | ion_vt_p
    x_item: str
    y_item: str
    x_unit: str = ""
    y_unit: str = ""
    x_spec: list[float | None]
    y_spec: list[float | None]
    points: list[WatScatterPoint]


class WatScatterPair(BaseModel):
    label: str
    plots: list[WatScatterPlot]


class WatSummaryResponse(BaseModel):
    product_id: str
    display_name: str
    lot_id: str
    measured_date: str = ""
    wafer_count: int
    items: list[WatItemStats]
    scatter_pairs: list[WatScatterPair]


class WatExportRequest(BaseModel):
    product_id: str
    lot_id: str


class WatLotPoint(BaseModel):
    """One lot's statistics for one item — a point on the trend chart."""
    lot_id: str
    measured_date: str
    n: int
    mean: float | None = None
    sigma: float | None = None
    cpk: float | None = None
    cpk_state: str          # "value" | "infinite" | "undefined"
    status: str             # "red" | "yellow" | "gray" | "ok"


class WatTrendItemStats(BaseModel):
    """Period-wide statistics for one item, pooled over every lot's raw site
    measurements — not an average of lot averages."""
    item_name: str
    unit: str = ""
    spec_low: float | None = None
    spec_high: float | None = None
    n: int
    mean: float | None = None
    sigma: float | None = None
    min: float | None = None
    max: float | None = None
    cpk: float | None = None
    cpk_state: str
    oos_count: int
    oos_pct: float
    status: str
    lot_series: list[WatLotPoint]


class WatTrendResponse(BaseModel):
    """`lots` is newest first (header strip); `lot_series` inside each item is
    oldest first (chart X axis). The two orders differ on purpose."""
    product_id: str
    display_name: str
    months: int
    start_date: str         # inclusive
    end_date: str           # exclusive
    lots: list[WatLotInfo]
    items: list[WatTrendItemStats]


class WatTrendExportRequest(BaseModel):
    product_id: str
    # Same bound as GET /wat/trend's Query(3, ge=1, le=6). Without it this
    # endpoint would accept any integer and drive an unbounded query plus a
    # per-item kaleido render.
    months: int = Field(3, ge=1, le=6)
