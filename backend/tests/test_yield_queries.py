"""Shape tests for the Report/PDF yield query builder.

CP and FT read the CP schema; SLT reads the FT schema (no SLT rows were ever
migrated into SEMI_CP_*). These assert the generated SQL without a database,
which is the only place the table/join wiring can be checked offline.
"""

import re

import pytest

from app.services.yield_queries import build_yield_query


def _sql(process: str, process_values=None) -> str:
    sql, _ = build_yield_query(process, ["P1"], process_values)
    return sql


def _where_clause(sql: str) -> str:
    return sql.split("WHERE", 1)[1]


def _on_clause(sql: str) -> str:
    """The ON clause: everything between ' ON ' and the WHERE keyword."""
    return sql.split("\n          ON ", 1)[1].split("WHERE", 1)[0]


@pytest.mark.parametrize("process", ["CP", "FT"])
def test_cp_and_ft_read_the_cp_schema(process):
    sql = _sql(process)
    assert "SEMI_CP_HEADER" in sql and "SEMI_CP_BIN_SUM" in sql
    assert "SEMI_FT_" not in sql
    assert "h.SUBSTRATE_ID                            AS substrate_id" in sql


def test_slt_reads_the_ft_schema():
    sql = _sql("SLT", ["cSLT1"])
    assert "SEMI_FT_HEADER" in sql and "SEMI_FT_BIN_SUM" in sql
    assert "SEMI_CP_" not in sql


def test_slt_joins_on_the_assembly_lot_and_exposes_it_as_substrate_id():
    """yield_aggregator dedupes each wafer's gross_die by substrate_id + wafer_id,
    so the FT lot key must arrive under that alias or the denominator collapses."""
    sql = _sql("SLT", ["cSLT1"])
    on = _on_clause(sql)
    assert "h.ASSY_LOT_ID = b.ASSY_LOT_ID" in on
    assert "h.PRODUCT_ID = b.PRODUCT_ID" in on
    assert "h.PROCESS = b.PROCESS" in on
    assert re.search(r"h\.ASSY_LOT_ID\s+AS substrate_id", sql)
    assert "SUBSTRATE_ID" not in sql


def test_slt_coalesces_wafer_id():
    """A NULL group key makes pandas drop the row, shrinking the gross-die
    denominator; FT/SLT is a package process where WAFER_ID may be NULL."""
    assert "COALESCE(TO_CHAR(h.WAFER_ID), '0')" in _sql("SLT", ["cSLT1"])


@pytest.mark.parametrize("process", ["CP", "FT", "SLT"])
def test_rework_new_is_filtered_on_both_tables(process):
    """Filtering one side lets the join fan out and double-count fail bins
    (yield% + sum(bin%) > 100%). See CLAUDE.md."""
    sql = _sql(process)
    assert re.search(r"h\.REWORK_NEW\s*=\s*0", sql)
    assert re.search(r"b\.REWORK_NEW\s*=\s*0", sql)


def test_slt_bin_predicates_live_in_the_on_clause():
    """Under a LEFT OUTER JOIN, a bin-side predicate in WHERE turns the outer
    join back into an inner one (NULL = 0 is never true), dropping exactly the
    zero-fail lots the outer join exists to keep."""
    sql = _sql("SLT", ["cSLT1"])
    assert "LEFT OUTER JOIN" in sql
    on, where = _on_clause(sql), _where_clause(sql)
    for pred in ("b.REWORK_NEW", "b.BIN_QUALITY", "b.BIN_NAME"):
        assert pred in on, f"{pred} must be in ON for an outer join"
        assert pred not in where, f"{pred} in WHERE collapses the outer join"


def test_cp_keeps_an_inner_join():
    sql = _sql("CP")
    assert "OUTER" not in sql
    assert "b.REWORK_NEW" in _where_clause(sql)


@pytest.mark.parametrize("process", ["CP", "FT", "SLT"])
def test_process_values_are_bound_not_interpolated(process):
    sql, binds = build_yield_query(process, ["P1"], ["cX1", "cX2"])
    assert binds["pv0"] == "cX1" and binds["pv1"] == "cX2"
    assert "cX1" not in sql


def test_unknown_process_builds_nothing():
    assert build_yield_query("WAT", ["P1"]) == ("", {})
