import logging

import pandas as pd
import pytest

from app.services.wat_trend_service import _lot_dates, build_lot_series, get_wat_trend


def _frame(rows):
    """rows: (lot_id, start_time, wafer_id, site_no, meas, spec_low, spec_high)"""
    return pd.DataFrame([
        {
            "lot_id": lot, "start_time": ts, "wafer_id": w, "site_no": s,
            "item_name": "ITEM", "item_unit": "V",
            "spec_low": lo, "spec_high": hi, "meas_data": v,
        }
        for lot, ts, w, s, v, lo, hi in rows
    ])


def test_lot_series_is_ordered_oldest_first():
    df = _frame([
        ("L3", "2026-08-01", 1, 1, 0.5, 0.0, 1.0),
        ("L1", "2026-06-01", 1, 1, 0.5, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 1, 0.5, 0.0, 1.0),
    ])
    series = build_lot_series(df, "ITEM", 0.0, 1.0, _lot_dates(df))
    assert [p["lot_id"] for p in series] == ["L1", "L2", "L3"]
    assert [p["measured_date"] for p in series] == [
        "2026-06-01", "2026-07-01", "2026-08-01",
    ]


def test_lot_series_sigma_is_none_for_a_single_measurement():
    df = _frame([("L1", "2026-06-01", 1, 1, 0.5, 0.0, 1.0)])
    series = build_lot_series(df, "ITEM", 0.0, 1.0, _lot_dates(df))
    assert series[0]["n"] == 1
    assert series[0]["sigma"] is None


def test_lot_series_flags_the_lot_that_went_out_of_spec():
    df = _frame([
        ("L1", "2026-06-01", 1, 1, 0.50, 0.0, 1.0),
        ("L1", "2026-06-01", 1, 2, 0.52, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 1, 0.50, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 2, 1.40, 0.0, 1.0),
    ])
    series = build_lot_series(df, "ITEM", 0.0, 1.0, _lot_dates(df))
    assert series[0]["status"] == "ok"
    assert series[1]["status"] == "red"


def test_period_stats_pool_raw_measurements_not_lot_means():
    """Two tight lots at different centers: pooling sees the spread between
    them, averaging lot means would not."""
    df = _frame([
        ("L1", "2026-06-01", 1, 1, 0.40, 0.0, 1.0),
        ("L1", "2026-06-01", 1, 2, 0.40, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 1, 0.60, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 2, 0.60, 0.0, 1.0),
    ])
    from app.services.wat_service import _item_core
    core = _item_core(df, "ITEM", 0.0, 1.0)
    assert core["n"] == 4
    assert core["mean"] == pytest.approx(0.5)
    assert core["sigma"] == pytest.approx(0.11547, rel=1e-3)   # not 0.0


def test_period_spec_conflict_takes_the_most_common_and_warns(caplog):
    df = _frame([
        ("L1", "2026-06-01", 1, 1, 0.5, 0.0, 1.0),
        ("L1", "2026-06-01", 1, 2, 0.5, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 1, 0.5, 0.0, 1.2),
    ])
    from app.services.wat_service import resolve_spec
    with caplog.at_level(logging.WARNING):
        assert resolve_spec(df["spec_high"], "ITEM") == 1.0
    assert "distinct spec values" in caplog.text


def test_get_wat_trend_reports_the_mock_products_items_and_lots():
    res = get_wat_trend("product_a", "P12345-A", 3)
    assert res.product_id
    assert res.months == 3
    assert len(res.items) == 30
    assert [i.item_name for i in res.items] == sorted(i.item_name for i in res.items)
    assert res.lots, "the mock product has lots in a 3-month window"
    # lots newest first, lot_series oldest first — deliberately opposite
    assert [l.last_measured for l in res.lots] == sorted(
        [l.last_measured for l in res.lots], reverse=True
    )
    series = res.items[0].lot_series
    assert [p.measured_date for p in series] == sorted(p.measured_date for p in series)
    assert len(series) == len(res.lots)


def test_get_wat_trend_still_flags_the_deliberate_mock_defects():
    res = get_wat_trend("product_a", "P12345-A", 3)
    by_name = {i.item_name: i for i in res.items}
    assert by_name["VTHN_ULVT"].status == "red"


def test_get_wat_trend_with_no_data_is_empty_not_an_error(monkeypatch):
    """Mock mode fabricates lots for any product id, so the no-data path has
    to be forced at the loader."""
    import app.services.wat_trend_service as svc
    monkeypatch.setattr(
        svc, "_load_trend", lambda pid, months, start, end: pd.DataFrame()
    )
    res = svc.get_wat_trend("product_a", "P12345-A", 3)
    assert res.items == []
    assert res.lots == []
    assert res.months == 3


def test_get_wat_trend_applies_the_periods_spec_to_every_lot(monkeypatch):
    """§4.2/§4.3 invariant: the spec is resolved once for the whole period
    and applied to every lot, never re-resolved per lot.

    Two lots carry the majority spec_high (1.0); L3 carries a different
    spec_high (1.3) whose own limit would judge its point "ok" (0.55 is
    still shy of 0.5 * 3-sigma... concretely: judged against 1.3 the point
    stays comfortably in-spec, judged against the period's 1.0 it goes out).
    If per-lot spec resolution ever crept back in, L3's point would flip to
    "ok" and this test would catch it.
    """
    import app.services.wat_trend_service as svc

    df = _frame([
        ("L1", "2026-06-01", 1, 1, 0.50, 0.0, 1.0),
        ("L1", "2026-06-01", 1, 2, 0.50, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 1, 0.50, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 2, 0.50, 0.0, 1.0),
        ("L3", "2026-08-01", 1, 1, 1.20, 0.0, 1.3),
        ("L3", "2026-08-01", 1, 2, 1.20, 0.0, 1.3),
    ])
    monkeypatch.setattr(
        svc, "_load_trend", lambda pid, months, start, end: df
    )
    res = svc.get_wat_trend("product_a", "P12345-A", 3)

    item = res.items[0]
    assert item.spec_high == 1.0, "period spec is the majority value, not L3's own"
    by_lot = {p.lot_id: p for p in item.lot_series}
    # 1.20 is in-spec against L3's own 1.3 limit but out-of-spec against the
    # period's 1.0 limit — only the latter should be applied.
    assert by_lot["L3"].status == "red"
