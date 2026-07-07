from unittest.mock import MagicMock

import app.services.lot_queries as lot_queries
from app.services.lot_queries import lot_column_for, build_lot_query, query_lot_data


def test_lot_column_for_cp_and_ft():
    # FT/SLT migrated into the CP schema → all share SUBSTRATE_ID
    assert lot_column_for("CP") == "SUBSTRATE_ID"
    assert lot_column_for("FT") == "SUBSTRATE_ID"
    assert lot_column_for("SLT") == "SUBSTRATE_ID"


def test_build_lot_query_selects_real_lot_column():
    sql, binds = build_lot_query(
        process="FT", product_ids=["P12345-A"],
        start_month="2025-12", end_month="2026-05", process_values=["cFT1"],
    )
    assert "SUBSTRATE_ID" in sql
    assert "SEMI_CP_HEADER" in sql           # FT now reads from the CP schema
    assert "AS lot_id" in sql
    assert "AS lot_date" in sql
    assert 'IYYY"W"IW' not in sql
    assert binds["start_month"] == "2025-12"
    assert "cFT1" in binds.values()


def test_build_lot_query_unknown_process_returns_empty_sql():
    sql, binds = build_lot_query("XX", ["x"], "2025-12", "2026-05", None)
    assert sql == ""


def test_query_lot_data_aligns_columns_with_select_order(monkeypatch):
    """Regression: result columns must match the SQL SELECT order so that
    bin_name strings don't land in the numeric bin_fail_count column.

    SELECT order is: lot_id, lot_date, wafer_id, yield_pct, gross_die,
    raw_bin_code, bin_name, bin_fail_count, test_program_rev.
    """
    db_row = (
        "LOT-001",       # lot_id
        "2026-05-01",    # lot_date
        7,               # wafer_id
        94.5,            # yield_pct
        1000,            # gross_die
        2,               # raw_bin_code
        "IDDQ2_LV",      # bin_name (a string!)
        12,              # bin_fail_count
        "REV01",         # test_program_rev
    )
    cursor = MagicMock()
    cursor.fetchall.return_value = [db_row]
    conn = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(lot_queries, "get_connection", lambda: conn)
    monkeypatch.setattr(lot_queries, "release_connection", lambda c: None)

    df = query_lot_data("FT", ["Q67890-A"], "2025-12", "2026-05")

    assert df.loc[0, "lot_id"] == "LOT-001"
    assert df.loc[0, "lot_date"] == "2026-05-01"
    assert df.loc[0, "bin_name"] == "IDDQ2_LV"
    assert int(df.loc[0, "bin_fail_count"]) == 12
    assert df.loc[0, "test_program_rev"] == "REV01"


def test_build_lot_query_partitions_lot_date_by_tp_rev():
    """Regression: lot_date must be MAX(date) per (lot, TP rev), so a lot whose
    wafers span multiple TP revs dates each rev by its own latest test date
    rather than inheriting the whole-lot MAX (which glued revs to one date)."""
    sql, _ = build_lot_query(
        process="CP", product_ids=["P12345-A"],
        start_month="2025-01", end_month="2025-06", process_values=["CP"],
    )
    assert "PARTITION BY h.SUBSTRATE_ID, h.REV01" in sql
