from datetime import date, timedelta

import pandas as pd

from app.models.schemas import ProcessData


def anchor_from_end_month(end_month: str) -> date:
    """Pick the 12-week window anchor: last day of end_month, capped at today."""
    year = int(end_month[:4])
    month = int(end_month[5:7])
    if month == 12:
        first_of_next = date(year + 1, 1, 1)
    else:
        first_of_next = date(year, month + 1, 1)
    last_of_month = first_of_next - timedelta(days=1)
    return min(last_of_month, date.today())


def latest_iso_weeks(anchor: date, n: int = 12) -> list[str]:
    """Return the n most recent ISO week labels (oldest → newest) ending at anchor's week.

    Format matches the DB-side TO_CHAR(..., 'IYYY"W"IW'), e.g. "2026W21".
    """
    iso = anchor.isocalendar()
    monday = date.fromisocalendar(iso[0], iso[1], 1)
    weeks: list[str] = []
    for i in range(n - 1, -1, -1):
        d = monday - timedelta(weeks=i)
        ic = d.isocalendar()
        weeks.append(f"{ic[0]}W{ic[1]:02d}")
    return weeks


def aggregate_lot_data(
    df: pd.DataFrame,
    target_lots: list[str] | None = None,
) -> ProcessData:
    """Aggregate a per-wafer DataFrame into lot-level ProcessData.

    If target_lots is provided, the result is re-indexed to that exact list of
    lot_ids (missing weeks get yield_avg=None and bin_pct=0), so charts always
    show a fixed number of week buckets even when data is sparse.
    """
    if df.empty:
        if target_lots:
            return ProcessData(
                lots=list(target_lots),
                yield_avg=[None] * len(target_lots),
                fail_bins={},
            )
        return ProcessData(lots=[], yield_avg=[], fail_bins={})

    yield_by_lot = df.groupby("lot_id")["yield_pct"].mean()

    lots = list(target_lots) if target_lots is not None else list(yield_by_lot.index)

    yield_avg: list[float | None] = []
    for lot in lots:
        if lot in yield_by_lot.index:
            yield_avg.append(round(float(yield_by_lot[lot]), 2))
        else:
            yield_avg.append(None)

    # Denominator = the lot's TOTAL gross die, counting each wafer's gross_die
    # ONCE. Summing gross_die over the (lot, bin) rows would count a wafer's
    # gross_die once per fail-bin row it has — and after bin-group mapping
    # collapses several raw bins into one group, that inflates the denominator
    # several-fold and makes bin% far too low. Mirror lot_service._aggregate.
    gross_by_lot = (
        df.groupby(["lot_id", "wafer_id"])["gross_die"].first()
        .groupby("lot_id").sum()
    )
    bin_data = (
        df.groupby(["lot_id", "bin_code"])["bin_fail_count"].sum()
        .reset_index(name="fail_sum")
    )
    bin_data["gross_sum"] = bin_data["lot_id"].map(gross_by_lot)
    bin_data["bin_pct"] = (
        bin_data["fail_sum"] / bin_data["gross_sum"].where(bin_data["gross_sum"] > 0) * 100
    ).round(3).fillna(0.0)

    pivot = (
        bin_data.pivot(index="lot_id", columns="bin_code", values="bin_pct")
        .fillna(0)
        .reindex(lots, fill_value=0)
    )

    fail_bins: dict[str, list[float]] = {
        str(bin_code): [round(float(v), 3) for v in pivot[bin_code].values]
        for bin_code in pivot.columns
    }

    return ProcessData(lots=lots, yield_avg=yield_avg, fail_bins=fail_bins)
