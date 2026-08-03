from app.services.mock_data import mock_wat_lots
from app.services.wat_service import get_wat_lots, get_wat_summary


def _first_lot(product_id="P12345-A"):
    return mock_wat_lots(product_id, 3)["lot_id"].iloc[-1]


def test_lots_are_returned_newest_first():
    res = get_wat_lots("product_a", "P12345-A", 3)
    dates = [l.last_measured for l in res.lots]
    assert dates == sorted(dates, reverse=True)
    assert res.product_id == "P12345-A"


def test_summary_items_are_sorted_by_item_name():
    res = get_wat_summary("product_a", "P12345-A", _first_lot())
    names = [i.item_name for i in res.items]
    assert names == sorted(names)
    assert len(names) == 30      # 6 flavors x 4 + 6 misc


def test_summary_reports_lot_metadata():
    lot = _first_lot()
    res = get_wat_summary("product_a", "P12345-A", lot)
    assert res.lot_id == lot
    assert res.wafer_count == 25
    assert res.measured_date


def test_summary_every_item_carries_wafer_series():
    res = get_wat_summary("product_a", "P12345-A", _first_lot())
    for item in res.items:
        assert len(item.wafer_series) == 25


def test_mock_exercises_red_and_yellow_paths():
    res = get_wat_summary("product_a", "P12345-A", _first_lot())
    statuses = {i.status for i in res.items}
    assert "red" in statuses, "mock must produce at least one red item"
    assert "yellow" in statuses, "mock must produce at least one yellow item"


def test_unknown_lot_returns_empty_summary_not_an_error():
    res = get_wat_summary("product_a", "P12345-A", "__no_such_lot__")
    assert res.items == []
    assert res.scatter_pairs == []
    assert res.wafer_count == 0


def test_product_without_wat_config_has_no_scatter_pairs(monkeypatch):
    import app.services.wat_service as ws
    monkeypatch.setattr(ws, "resolve_wat_pairs", lambda nickname: [])
    res = get_wat_summary("product_a", "P12345-A", _first_lot())
    assert res.scatter_pairs == []
    assert res.items, "the table must still render without a wat: block"


_REALISTIC_WAT_PAIR = [{
    "label": "Core RVT",
    "vth_n": "VTHN_RVT",
    "vth_p": "VTHP_RVT",
    "idsat_n": "IDSATN_RVT",
    "idsat_p": "IDSATP_RVT",
}]


def test_unknown_lot_with_wat_config_still_returns_empty_scatter_pairs(monkeypatch):
    """An unknown/empty lot must yield an empty summary even when the product
    HAS a configured wat: block — build_scatter_pairs alone doesn't know the
    lot has no data, so get_wat_summary must guard on the empty frame."""
    import app.services.wat_service as ws
    monkeypatch.setattr(ws, "resolve_wat_pairs", lambda nickname: _REALISTIC_WAT_PAIR)
    res = get_wat_summary("product_a", "P12345-A", "__no_such_lot__")
    assert res.items == []
    assert res.scatter_pairs == []
    assert res.wafer_count == 0


def test_scatter_pairs_populate_for_a_real_lot_with_wat_config(monkeypatch):
    """With a configured wat: block and a lot that has data, scatter_pairs
    must actually be populated and the nested pydantic models must coerce
    the service's plain-dict output without a ValidationError."""
    import app.services.wat_service as ws
    monkeypatch.setattr(ws, "resolve_wat_pairs", lambda nickname: _REALISTIC_WAT_PAIR)
    res = get_wat_summary("product_a", "P12345-A", _first_lot())
    assert len(res.scatter_pairs) == 1
    pair = res.scatter_pairs[0]
    assert pair.label == "Core RVT"
    assert [p.kind for p in pair.plots] == ["vth_np", "idsat_np", "ion_vt_n", "ion_vt_p"]
    for plot in pair.plots:
        assert plot.points, f"{plot.kind} should have points for a real lot"
