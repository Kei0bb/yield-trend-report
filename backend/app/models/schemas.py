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
