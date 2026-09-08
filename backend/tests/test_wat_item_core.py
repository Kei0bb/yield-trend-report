import pandas as pd

from app.models.schemas import (
    WatLotPoint, WatTrendItemStats, WatTrendResponse,
)
from app.services.mock_data import mock_wat_lots
from app.services.wat_service import _item_core, compute_item_stats, get_wat_summary


def _group(values, spec_low=0.0, spec_high=1.0):
    return pd.DataFrame({
        "wafer_id": [1] * len(values),
        "site_no": list(range(1, len(values) + 1)),
        "item_name": ["ITEM"] * len(values),
        "item_unit": ["V"] * len(values),
        "spec_low": [spec_low] * len(values),
        "spec_high": [spec_high] * len(values),
        "meas_data": values,
    })


def test_item_core_carries_every_scalar_column_but_no_series():
    core = _item_core(_group([0.4, 0.5, 0.6]), "ITEM", 0.0, 1.0)
    assert set(core) == {
        "item_name", "unit", "spec_low", "spec_high", "n", "mean", "sigma",
        "min", "max", "cpk", "cpk_state", "oos_count", "oos_pct", "status",
    }


def test_item_core_uses_the_spec_it_is_given_not_the_frame():
    """The trend path resolves one spec for the whole period and applies it to
    every lot; a per-lot re-resolve would let a chart's spec line disagree with
    the point judged against it."""
    group = _group([0.4, 0.5, 0.6], spec_low=0.0, spec_high=1.0)
    core = _item_core(group, "ITEM", 0.45, 0.55)
    assert core["spec_low"] == 0.45
    assert core["spec_high"] == 0.55
    assert core["oos_count"] == 2      # 0.4 and 0.6 are outside 0.45..0.55
    assert core["status"] == "red"


def test_compute_item_stats_still_returns_the_wafer_series():
    stats = compute_item_stats(_group([0.4, 0.5, 0.6]), "ITEM")
    assert stats["item_name"] == "ITEM"
    assert [w["wafer_id"] for w in stats["wafer_series"]] == [1]


def test_get_wat_summary_output_is_unchanged_by_the_extraction():
    """Regression guard: the single-lot report must not shift at all."""
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    summary = get_wat_summary("product_a", "P12345-A", lot)
    assert len(summary.items) == 30
    vthn = next(i for i in summary.items if i.item_name == "VTHN_ULVT")
    assert vthn.status == "red"
    assert len(vthn.wafer_series) == 25


def test_trend_models_accept_a_minimal_payload():
    point = WatLotPoint(
        lot_id="LOT-1", measured_date="2026-06-14", n=225,
        mean=0.45, sigma=0.02, cpk=1.2, cpk_state="value", status="yellow",
    )
    item = WatTrendItemStats(
        item_name="VTHN_RVT", unit="V", spec_low=0.3, spec_high=0.6,
        n=225, mean=0.45, sigma=0.02, min=0.4, max=0.5,
        cpk=1.2, cpk_state="value", oos_count=0, oos_pct=0.0,
        status="yellow", lot_series=[point],
    )
    res = WatTrendResponse(
        product_id="P12345-A", display_name="Product A", months=3,
        start_date="2026-06-09", end_date="2026-09-08", lots=[], items=[item],
    )
    assert res.items[0].lot_series[0].lot_id == "LOT-1"
