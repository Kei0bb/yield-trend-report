from types import SimpleNamespace

from app.services.anomaly_service import evaluate

CFG = {"bin_surge": {"delta_pct": 3.0}}


def _lot(yield_pct, bins=None):
    bins = bins or []
    bb = [SimpleNamespace(bin_name=n, percent=p, bin_codes=c) for (n, p, c) in bins]
    return SimpleNamespace(yield_pct=yield_pct, bin_breakdown=bb)


def test_no_warning_when_stable():
    lots = [_lot(95.0), _lot(95.2), _lot(94.8), _lot(95.1)]
    assert evaluate(lots, CFG) == []


def test_yield_drop_alone_raises_no_warning():
    # Yield alerts were removed: the Dashboard shows the delta in its own column.
    lots = [_lot(95.0), _lot(95.0), _lot(95.0), _lot(60.0)]
    assert evaluate(lots, CFG) == []


def test_only_bin_surge_warnings_are_emitted():
    # A yield collapse next to a bin surge yields exactly one (bin) warning.
    past = [("Short", 1.0, [5])]
    latest = [("Short", 5.0, [5])]
    lots = [_lot(95.0, past), _lot(95.0, past), _lot(95.0, past), _lot(60.0, latest)]
    warns = evaluate(lots, CFG)
    assert [w["type"] for w in warns] == ["bin_surge"]


def test_bin_surge_triggers():
    # past avg ~1%, latest 5% → delta 4%pt >= 3.0%pt → triggers
    past = [("Short", 1.0, [5])]
    latest = [("Short", 5.0, [5])]
    lots = [_lot(95.0, past), _lot(95.0, past), _lot(95.0, past), _lot(95.0, latest)]
    warns = [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"]
    assert len(warns) == 1
    assert warns[0]["bin_code"] == 5
    assert "▲4.0%" in warns[0]["message"]


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
    # Verify the badge message format (triangle glyph, no "vs avg" suffix —
    # the Dashboard column header carries the comparison basis)
    past = [("Open", 2.0, [3])]
    latest = [("Open", 7.0, [3])]
    lots = [_lot(90.0, past), _lot(90.0, past), _lot(90.0, past), _lot(90.0, latest)]
    warns = [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"]
    assert len(warns) == 1
    assert warns[0]["message"] == "Open ▲5.0%"


def test_empty_or_single_lot_returns_empty():
    assert evaluate([], CFG) == []
    assert evaluate([_lot(95.0)], CFG) == []


def test_intermittent_bin_averages_absences_as_zero():
    # 10 past lots: one at 5%, nine absent (0%) -> avg should be 0.5%, not 5.0%.
    # latest 8% -> delta 7.5%pt >= 3.0%pt -> triggers, with the correct delta.
    past_lots = [_lot(95.0, [("Short", 5.0, [5])])] + [_lot(95.0, []) for _ in range(9)]
    lots = past_lots + [_lot(95.0, [("Short", 8.0, [5])])]
    warns = [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"]
    assert len(warns) == 1
    assert warns[0]["message"] == "Short ▲7.5%"


def test_new_bin_never_seen_before_triggers():
    # A fail bin absent from every past lot has an implicit past average of 0%.
    past_lots = [_lot(95.0, [("Open", 1.0, [3])])] * 3
    lots = past_lots + [_lot(95.0, [("Open", 1.0, [3]), ("Short", 10.0, [5])])]
    warns = [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"]
    assert [w["message"] for w in warns] == ["Short ▲10.0%"]
    assert warns[0]["bin_code"] == 5


def test_new_bin_small_value_does_not_trigger():
    past_lots = [_lot(95.0, [("Open", 1.0, [3])])] * 3
    lots = past_lots + [_lot(95.0, [("Open", 1.0, [3]), ("Short", 2.0, [5])])]
    warns = [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"]
    assert warns == []
