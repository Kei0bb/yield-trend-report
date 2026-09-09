import pandas as pd

from app.services.mock_data import (
    mock_wat_dataframe, mock_wat_lots, mock_wat_trend_dataframe,
)
from app.services.wat_queries import WAT_TREND_COLUMNS


def test_trend_frame_covers_every_lot_in_the_period():
    lots = mock_wat_lots("P12345-A", 3)
    df = mock_wat_trend_dataframe("P12345-A", 3)
    assert set(df["lot_id"]) == set(lots["lot_id"])


def test_trend_frame_column_order_matches_the_query():
    df = mock_wat_trend_dataframe("P12345-A", 3)
    assert list(df.columns) == WAT_TREND_COLUMNS


def test_trend_frame_rows_match_the_single_lot_frame():
    """Same generator, so a lot's rows must not change when read via trend."""
    lot = str(mock_wat_lots("P12345-A", 3)["lot_id"].iloc[0])
    single = mock_wat_dataframe("P12345-A", lot)
    trend = mock_wat_trend_dataframe("P12345-A", 3)
    subset = trend[trend["lot_id"] == lot]
    assert len(subset) == len(single)
    assert subset["meas_data"].sum() == single["meas_data"].sum()


def test_trend_frame_is_deterministic():
    a = mock_wat_trend_dataframe("P12345-A", 3)
    b = mock_wat_trend_dataframe("P12345-A", 3)
    assert a.equals(b)


def test_trend_frame_is_empty_when_the_period_holds_no_lots(monkeypatch):
    """The mock lot generator fabricates lots for ANY product id, so the empty
    path has to be forced — a made-up product id would not reach it."""
    import app.services.mock_data as mock_data
    monkeypatch.setattr(
        mock_data, "mock_wat_lots",
        lambda pid, months: pd.DataFrame(columns=mock_data.WAT_LOT_COLUMNS),
    )
    df = mock_data.mock_wat_trend_dataframe("P12345-A", 3)
    assert df.empty
    assert list(df.columns) == WAT_TREND_COLUMNS
