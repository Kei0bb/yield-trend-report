from app.services.lot_service import get_lots, period_months


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
