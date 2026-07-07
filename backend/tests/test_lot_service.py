import pandas as pd

from app.services.lot_queries import LOT_COLUMNS
from app.services.lot_service import _aggregate, get_lots, period_months


def test_period_months_returns_start_end():
    start, end = period_months(6)
    assert len(start) == 7 and start[4] == "-"
    assert len(end) == 7


def test_get_lots_returns_sorted_lotdata():
    lots = get_lots("Product-A", "CP", months=6)
    assert len(lots) > 1
    dates = [l.lot_date for l in lots]
    assert dates == sorted(dates)
    latest = lots[-1]
    assert latest.wafer_count >= 1
    assert 0 <= latest.yield_pct <= 100
    assert latest.bin_breakdown


def test_get_lots_attaches_warnings_to_latest_only():
    lots = get_lots("Product-A", "CP", months=6)
    assert lots[-1].warnings
    assert all(not l.warnings for l in lots[:-1])


def test_get_lots_unknown_process_returns_empty():
    assert get_lots("Product-A", "ZZ", months=6) == []


def test_aggregate_split_by_rev_dates_each_rev_independently():
    """A lot spanning two TP revs splits into two LotData rows, each dated by
    its own rev's MAX test date (not the whole-lot date), sorted oldest→newest."""
    rows = [
        ("LOT1", "2025-01-10", 1, 95.0, 1000, 2, "BINA", 50,  "PROG_REV01"),
        ("LOT1", "2025-03-20", 2, 90.0, 1000, 2, "BINA", 100, "PROG_REV02"),
        ("LOT1", "2025-03-25", 3, 88.0, 1000, 2, "BINA", 80,  "PROG_REV02"),
    ]
    df = pd.DataFrame(rows, columns=LOT_COLUMNS)
    lots = _aggregate(df, bin_group="default", process="CP", raw_bins=True, split_by_rev=True)
    assert len(lots) == 2
    # REV02's row is dated by its MAX date (2025-03-25), proving .max() (not .iloc[0]).
    assert [l.lot_date for l in lots] == ["2025-01-10", "2025-03-25"]
    assert lots[0].test_program_rev.endswith("REV01")
    assert lots[1].test_program_rev.endswith("REV02")
    assert lots[1].wafer_count == 2
