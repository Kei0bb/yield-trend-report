from types import SimpleNamespace

from app.services.anomaly_service import evaluate

CFG = {
    "yield_drop": {"threshold_pct": 3.0, "min_lots": 3},
    "bin_surge": {"delta_pct": 3.0},
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
    # past avg ~1%, latest 5% → delta 4%pt >= 3.0%pt → triggers
    past = [("Short", 1.0, [5])]
    latest = [("Short", 5.0, [5])]
    lots = [_lot(95.0, past), _lot(95.0, past), _lot(95.0, past), _lot(95.0, latest)]
    warns = [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"]
    assert len(warns) == 1
    assert warns[0]["bin_code"] == 5
    assert "+4.0%pt" in warns[0]["message"]


def test_bin_surge_does_not_trigger_just_below_delta():
    # past avg 1%, latest 3.9% → delta 2.9%pt < 3.0%pt → no trigger
    past = [("Short", 1.0, [5])]
    latest = [("Short", 3.9, [5])]
    lots = [_lot(95.0, past), _lot(95.0, past), _lot(95.0, past), _lot(95.0, latest)]
    assert [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"] == []


def test_bin_surge_small_delta_does_not_trigger():
    # Even with a low baseline (0.2%), a small absolute rise (0.7%pt) does not fire
    past = [("Leak", 0.2, [7])]
    latest = [("Leak", 0.9, [7])]
    lots = [_lot(95.0, past), _lot(95.0, past), _lot(95.0, past), _lot(95.0, latest)]
    assert [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"] == []


def test_bin_surge_exact_threshold_triggers():
    # past avg 1%, latest 4% → delta exactly 3.0%pt → triggers (>= boundary)
    past = [("Short", 1.0, [5])]
    latest = [("Short", 4.0, [5])]
    lots = [_lot(95.0, past), _lot(95.0, past), _lot(95.0, past), _lot(95.0, latest)]
    warns = [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"]
    assert len(warns) == 1


def test_bin_surge_message_format():
    # Verify the new absolute-pt message format
    past = [("Open", 2.0, [3])]
    latest = [("Open", 7.0, [3])]
    lots = [_lot(90.0, past), _lot(90.0, past), _lot(90.0, past), _lot(90.0, latest)]
    warns = [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"]
    assert len(warns) == 1
    assert warns[0]["message"] == "Open +5.0%pt vs prior avg"


def test_empty_or_single_lot_returns_empty():
    assert evaluate([], CFG) == []
    assert evaluate([_lot(95.0)], CFG) == []
