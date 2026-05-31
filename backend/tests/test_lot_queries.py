from app.services.lot_queries import lot_column_for, build_lot_query


def test_lot_column_for_cp_and_ft():
    assert lot_column_for("CP") == "SUBSTRATE_ID"
    assert lot_column_for("FT") == "ASSY_LOT_ID"
    assert lot_column_for("SLT") == "ASSY_LOT_ID"


def test_build_lot_query_selects_real_lot_column():
    sql, binds = build_lot_query(
        process="FT", product_ids=["Q67890-A"],
        start_month="2025-12", end_month="2026-05", process_values=None,
    )
    assert "ASSY_LOT_ID" in sql
    assert "AS lot_id" in sql
    assert "AS lot_date" in sql
    assert 'IYYY"W"IW' not in sql
    assert binds["start_month"] == "2025-12"


def test_build_lot_query_unknown_process_returns_empty_sql():
    sql, binds = build_lot_query("XX", ["x"], "2025-12", "2026-05", None)
    assert sql == ""
