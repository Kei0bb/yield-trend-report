from app.models.schemas import (
    BinBreakdown, LotData, Warning, SparkPoint, SummaryRow,
    ExploreLotsResponse, DashboardSummaryResponse,
)


def test_lotdata_roundtrip():
    lot = LotData(
        lot_id="LOT-1", lot_date="2026-05-25", wafer_count=25, yield_pct=87.5,
        bin_breakdown=[BinBreakdown(bin_name="Short", bin_codes=[5], count=10, percent=4.0)],
        warnings=[Warning(type="yield_drop", message="x")],
    )
    dumped = lot.model_dump()
    assert dumped["yield_pct"] == 87.5
    assert dumped["bin_breakdown"][0]["bin_name"] == "Short"
    assert dumped["warnings"][0]["severity"] == "warn"


def test_summary_row_defaults():
    row = SummaryRow(
        nickname="P", product_id="P12345", display_name="P", process="CP",
        latest_yield=None, latest_lot_id=None, latest_lot_date=None,
        avg_yield_6m=None, delta=None, sparkline=[], warnings=[],
    )
    assert row.sparkline == []
