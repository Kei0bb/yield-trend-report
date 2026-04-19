from pydantic import BaseModel


class YieldRequest(BaseModel):
    product: str
    start_month: str  # "YYYY-MM"
    end_month: str  # "YYYY-MM"
    processes: list[str]  # ["CP", "FT", "SLT"]


class ProcessData(BaseModel):
    lots: list[str]
    yield_avg: list[float]
    fail_bins: dict[str, list[float]]  # bin_name -> per-lot bin%


class YieldResponse(BaseModel):
    data: dict[str, ProcessData]  # process_name -> ProcessData
