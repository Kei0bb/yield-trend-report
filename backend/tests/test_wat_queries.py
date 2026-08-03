from datetime import date

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
