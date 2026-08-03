from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import app.services.wat_queries as wat_queries
from app.services.wat_queries import (
    WAT_DETAIL_COLUMNS, WAT_LOT_COLUMNS, WAT_TABLE,
    build_wat_detail_query, build_wat_lots_query,
)


def test_lots_query_binds_product_and_period():
    sql, binds = build_wat_lots_query("P12345-A", date(2026, 5, 1), date(2026, 7, 29))
    assert WAT_TABLE in sql
    assert binds == {"pid": "P12345-A", "start": date(2026, 5, 1), "end": date(2026, 7, 29)}
    assert ":pid" in sql and ":start" in sql and ":end" in sql


def test_lots_query_upper_bound_is_exclusive():
    sql, _ = build_wat_lots_query("P", date(2026, 1, 1), date(2026, 2, 1))
    assert "START_TIME >= :start" in sql
    assert "START_TIME <  :end" in sql or "START_TIME < :end" in sql


def test_lots_query_orders_newest_last_by_max_start_time():
    sql, _ = build_wat_lots_query("P", date(2026, 1, 1), date(2026, 2, 1))
    assert "GROUP BY LOT_ID" in sql
    assert "ORDER BY MAX(START_TIME)" in sql


def test_lots_query_column_order_matches_select():
    sql, _ = build_wat_lots_query("P", date(2026, 1, 1), date(2026, 2, 1))
    select_body = sql.split("FROM")[0]
    for i, col in enumerate(WAT_LOT_COLUMNS):
        assert col in select_body, f"{col} missing from SELECT"


def test_detail_query_binds_product_and_lot():
    sql, binds = build_wat_detail_query("P12345-A", "LOT-1")
    assert binds == {"pid": "P12345-A", "lot": "LOT-1"}
    assert "PRODUCT_ID = :pid" in sql
    assert "LOT_ID = :lot" in sql


def test_detail_query_does_not_filter_rework_or_del_flag():
    """This process has no rework; filtering would silently drop valid rows."""
    sql, _ = build_wat_detail_query("P", "L")
    assert "REWORK" not in sql.upper()
    assert "DEL_FLAG" not in sql.upper()


def test_detail_query_column_order_matches_select():
    sql, _ = build_wat_detail_query("P", "L")
    select_body = sql.split("FROM")[0]
    positions = [select_body.index(col) for col in WAT_DETAIL_COLUMNS]
    assert positions == sorted(positions), "SELECT order must match WAT_DETAIL_COLUMNS"


def test_empty_inputs_produce_no_sql():
    assert build_wat_lots_query("", date(2026, 1, 1), date(2026, 2, 1)) == ("", {})
    assert build_wat_detail_query("P", "") == ("", {})
    assert build_wat_detail_query("", "L") == ("", {})


# ---------------------------------------------------------------------------
# '%' wildcard product_id (product_config.yaml LIKE support)
# ---------------------------------------------------------------------------

def test_lots_query_uses_like_for_wildcard_product_id():
    sql, binds = build_wat_lots_query("SC0G29AP3%", date(2026, 1, 1), date(2026, 2, 1))
    assert "PRODUCT_ID LIKE :pid" in sql
    assert "PRODUCT_ID = :pid" not in sql
    assert binds["pid"] == "SC0G29AP3%"


def test_lots_query_uses_equality_for_plain_product_id():
    sql, binds = build_wat_lots_query("P12345-A", date(2026, 1, 1), date(2026, 2, 1))
    assert "PRODUCT_ID = :pid" in sql
    assert "LIKE" not in sql.upper()
    assert binds["pid"] == "P12345-A"


def test_detail_query_uses_like_for_wildcard_product_id():
    sql, binds = build_wat_detail_query("SC0G29AP3%", "LOT-1")
    assert "PRODUCT_ID LIKE :pid" in sql
    assert "PRODUCT_ID = :pid" not in sql
    assert binds["pid"] == "SC0G29AP3%"


def test_detail_query_uses_equality_for_plain_product_id():
    sql, binds = build_wat_detail_query("P12345-A", "LOT-1")
    assert "PRODUCT_ID = :pid" in sql
    assert "LIKE" not in sql.upper()
    assert binds["pid"] == "P12345-A"


# ---------------------------------------------------------------------------
# Real-DB shape normalisation: padded CHAR strings and Decimal measurements
# ---------------------------------------------------------------------------

def test_query_wat_detail_strips_padded_names_and_coerces_decimal(monkeypatch):
    """Oracle CHAR columns arrive space-padded, and MEAS_DATA/SPEC_* can
    arrive as decimal.Decimal — either would break downstream matching
    (item_name lookup) or stats (Series.std(ddof=1) on object dtype)."""
    row = (1, 1, "VTHN_RVT   ", "V   ", Decimal("0.10"), Decimal("0.90"),
           Decimal("0.45"), "2026-01-01")
    cursor = MagicMock()
    cursor.fetchall.return_value = [row]
    conn = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(wat_queries, "get_connection", lambda: conn)
    monkeypatch.setattr(wat_queries, "release_connection", lambda c: None)

    df = wat_queries.query_wat_detail("P12345-A", "LOT-1")

    assert df.loc[0, "item_name"] == "VTHN_RVT"
    assert df.loc[0, "item_unit"] == "V"
    assert df["meas_data"].dtype.kind == "f"
    assert df["spec_low"].dtype.kind == "f"
    assert df["spec_high"].dtype.kind == "f"
    assert df.loc[0, "meas_data"] == 0.45
    # Would raise TypeError before the fix: std(ddof=1) on object dtype.
    df["meas_data"].std(ddof=1)
