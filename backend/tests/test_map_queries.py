from unittest.mock import MagicMock

import app.services.map_queries as map_queries
from app.services.map_queries import (
    BIN_META_COLUMNS,
    DIE_COLUMNS,
    build_bin_meta_query,
    build_die_map_query,
    query_bin_meta,
    query_die_map,
)


def test_build_die_map_query_single_table_no_join():
    sql, binds = build_die_map_query(["LOTA", "LOTB"], ["CP1", "CP2"])
    assert "SEMI_CP_BIN_DETAIL" in sql
    assert "JOIN" not in sql.upper()
    assert "SEMI_CP_HEADER" not in sql
    assert "BIN_QUALITY" not in sql
    assert "REWORK_NEW = 0" in sql
    # every lot and process value is bound, none inlined
    assert set(binds.values()) == {"LOTA", "LOTB", "CP1", "CP2"}
    assert "LOTA" not in sql


def test_build_die_map_query_empty_lots_returns_empty_sql():
    sql, binds = build_die_map_query([], ["CP"])
    assert sql == ""


def test_query_die_map_aligns_columns_with_select_order(monkeypatch):
    db_row = ("LOTA", "7", 3, -5, 13)
    cursor = MagicMock()
    cursor.fetchall.return_value = [db_row]
    conn = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(map_queries, "get_connection", lambda: conn)
    monkeypatch.setattr(map_queries, "release_connection", lambda c: None)

    df = query_die_map(["LOTA"], ["CP"])
    assert list(df.columns) == DIE_COLUMNS
    assert df.loc[0, "lot_id"] == "LOTA"
    assert int(df.loc[0, "x"]) == 3
    assert int(df.loc[0, "y"]) == -5
    assert int(df.loc[0, "bin_code"]) == 13


def test_build_bin_meta_query_single_table_from_bin_sum():
    sql, binds = build_bin_meta_query(["LOTA", "LOTB"], ["CP1", "CP2"])
    assert "SEMI_CP_BIN_SUM" in sql
    assert "JOIN" not in sql.upper()
    assert "SEMI_CP_BIN_DETAIL" not in sql
    assert "REWORK_NEW = 0" in sql
    assert "DISTINCT" in sql.upper()
    # every lot and process value is bound, none inlined
    assert set(binds.values()) == {"LOTA", "LOTB", "CP1", "CP2"}
    assert "LOTA" not in sql


def test_build_bin_meta_query_empty_lots_returns_empty_sql():
    sql, binds = build_bin_meta_query([], ["CP"])
    assert sql == ""


def test_query_bin_meta_aligns_columns_with_select_order(monkeypatch):
    db_row = (13, "VDD_Short", "FAIL")
    cursor = MagicMock()
    cursor.fetchall.return_value = [db_row]
    conn = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(map_queries, "get_connection", lambda: conn)
    monkeypatch.setattr(map_queries, "release_connection", lambda c: None)

    df = query_bin_meta(["LOTA"], ["CP"])
    assert list(df.columns) == BIN_META_COLUMNS
    assert int(df.loc[0, "bin_code"]) == 13
    assert df.loc[0, "bin_name"] == "VDD_Short"
    assert df.loc[0, "bin_quality"] == "FAIL"
