from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pandas as pd

import app.services.wat_queries as wat_queries
from app.services.wat_queries import (
    WAT_TABLE, WAT_TREND_COLUMNS, build_wat_trend_query,
)


def test_trend_query_binds_product_and_period():
    sql, binds = build_wat_trend_query("P12345-A", date(2026, 6, 9), date(2026, 9, 8))
    assert WAT_TABLE in sql
    assert binds == {
        "pid": "P12345-A",
        "start_dt": date(2026, 6, 9),
        "end_dt": date(2026, 9, 8),
    }


def test_trend_query_uses_equality_without_a_wildcard():
    sql, _ = build_wat_trend_query("P12345-A", date(2026, 1, 1), date(2026, 2, 1))
    assert "PRODUCT_ID = :pid" in sql
    assert "LIKE" not in sql


def test_trend_query_uses_like_with_a_wildcard():
    sql, _ = build_wat_trend_query("SC0G29B%", date(2026, 1, 1), date(2026, 2, 1))
    assert "PRODUCT_ID LIKE :pid" in sql


def test_trend_query_upper_bound_is_exclusive():
    sql, _ = build_wat_trend_query("P", date(2026, 1, 1), date(2026, 2, 1))
    assert "START_TIME >= :start_dt" in sql
    assert "START_TIME <  :end_dt" in sql or "START_TIME < :end_dt" in sql


def test_trend_query_selects_every_declared_column():
    sql, _ = build_wat_trend_query("P", date(2026, 1, 1), date(2026, 2, 1))
    select_body = sql.split("FROM")[0]
    for col in WAT_TREND_COLUMNS:
        assert col in select_body, f"{col} missing from SELECT"


def test_trend_query_is_empty_without_a_product_id():
    assert build_wat_trend_query("", date(2026, 1, 1), date(2026, 2, 1)) == ("", {})


def test_query_wat_trend_returns_empty_frame_without_a_product_id():
    df = wat_queries.query_wat_trend("", date(2026, 1, 1), date(2026, 2, 1))
    assert df.empty
    assert list(df.columns) == WAT_TREND_COLUMNS


def test_query_wat_trend_normalizes_padded_text_and_decimals(monkeypatch):
    """Oracle CHAR pads with spaces and can hand back decimal.Decimal.

    Unstripped names never match the configured `wat: pairs`, and an
    object-dtype column breaks Series.std(ddof=1) downstream.
    """
    rows = [(
        "LOT-1  ", 3, 5, "VTHN_RVT  ", "V  ",
        Decimal("0.30"), Decimal("0.60"), Decimal("0.45"), "2026-06-14",
    )]
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(wat_queries, "get_connection", lambda: conn)
    monkeypatch.setattr(wat_queries, "release_connection", lambda c: None)

    df = wat_queries.query_wat_trend("P", date(2026, 1, 1), date(2026, 2, 1))

    assert df["lot_id"].iloc[0] == "LOT-1"
    assert df["item_name"].iloc[0] == "VTHN_RVT"
    assert df["item_unit"].iloc[0] == "V"
    assert pd.api.types.is_numeric_dtype(df["meas_data"])
    assert pd.api.types.is_numeric_dtype(df["spec_low"])
    assert pd.api.types.is_numeric_dtype(df["spec_high"])
