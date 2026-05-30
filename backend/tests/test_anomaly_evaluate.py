from types import SimpleNamespace

from app.services.anomaly_service import evaluate

CFG = {
    "yield_drop": {"threshold_pct": 3.0, "min_lots": 3},
    "bin_surge": {"multiplier": 2.0, "min_percent": 1.0},
}


def _lot(yield_pct, bins=None):
    bins = bins or []
    bb = [SimpleNamespace(bin_name=n, percent=p, bin_codes=c) for (n, p, c) in bins]
    return SimpleNamespace(yield_pct=yield_pct, bin_breakdown=bb)


def test_no_warning_when_stable():
    lots = [_lot(95.0), _lot(95.2), _lot(94.8), _lot(95.1)]
    assert evaluate(lots, CFG) == []


def test_yield_drop_triggers():
    lots = [_lot(95.0), _lot(95.0), _lot(95.0), _lot(90.0)]
    warns = evaluate(lots, CFG)
    types = [w["type"] for w in warns]
    assert "yield_drop" in types


def test_yield_drop_skipped_when_too_few_past_lots():
    lots = [_lot(95.0), _lot(95.0), _lot(80.0)]
    assert [w for w in evaluate(lots, CFG) if w["type"] == "yield_drop"] == []


def test_bin_surge_triggers():
    past = [("Short", 1.0, [5])]
    latest = [("Short", 3.0, [5])]
    lots = [_lot(95.0, past), _lot(95.0, past), _lot(95.0, past), _lot(95.0, latest)]
    warns = [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"]
    assert len(warns) == 1
    assert warns[0]["bin_code"] == 5


def test_bin_surge_ignores_tiny_baseline():
    past = [("Leak", 0.2, [7])]
    latest = [("Leak", 0.9, [7])]
    lots = [_lot(95.0, past), _lot(95.0, past), _lot(95.0, past), _lot(95.0, latest)]
    assert [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"] == []


def test_empty_or_single_lot_returns_empty():
    assert evaluate([], CFG) == []
    assert evaluate([_lot(95.0)], CFG) == []
