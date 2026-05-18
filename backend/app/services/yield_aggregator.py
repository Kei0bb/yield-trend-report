import pandas as pd

from app.models.schemas import ProcessData


def aggregate_lot_data(df: pd.DataFrame) -> ProcessData:
    """Aggregate a per-wafer DataFrame into lot-level ProcessData.

    Input columns (from yield_queries.COMMON_COLUMNS after bin_code mapping):
        lot_id, wafer_id, yield_pct, gross_die, raw_bin_code, bin_name, bin_code, bin_fail_count

    Aggregation:
    - yield_avg: mean of wafer yields per lot
    - fail_bins: bin_fail_count / gross_die * 100, pivoted to {bin_name: [per-lot values]}
    """
    if df.empty:
        return ProcessData(lots=[], yield_avg=[], fail_bins={})

    yield_by_lot = df.groupby("lot_id")["yield_pct"].mean()
    lots = list(yield_by_lot.index)
    yield_avg = [round(float(v), 2) for v in yield_by_lot.values]

    bin_data = (
        df.groupby(["lot_id", "bin_code"])
        .agg(fail_sum=("bin_fail_count", "sum"), gross_sum=("gross_die", "sum"))
        .reset_index()
    )
    bin_data["bin_pct"] = (bin_data["fail_sum"] / bin_data["gross_sum"] * 100).round(3)

    pivot = (
        bin_data.pivot(index="lot_id", columns="bin_code", values="bin_pct")
        .fillna(0)
        .reindex(lots)
    )

    fail_bins: dict[str, list[float]] = {
        str(bin_code): [round(float(v), 3) for v in pivot[bin_code].values]
        for bin_code in pivot.columns
    }

    return ProcessData(lots=lots, yield_avg=yield_avg, fail_bins=fail_bins)
