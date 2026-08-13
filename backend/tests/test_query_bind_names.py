"""Guard against ORA-01745: bind variable names that are Oracle reserved words.

oracledb accepts `:start` / `:end` when the statement is built and only rejects
them at execute() time, against a real database. Every other test in this suite
builds SQL or uses mock data, so a reserved-word bind name reaches production
untouched — which is exactly how the WAT lot query shipped broken.

Two passes, because bind names arrive two ways:
  - literal `:name` written into a SQL f-string (wat/lot/yield queries)
  - generated per item, e.g. lot0 / pv0 / pid0 (map/lot/yield queries) — these
    never appear as `:name` in the source, so the builders are called and their
    returned bind dicts inspected.
"""

import ast
import pathlib
import re
from datetime import date

import pytest

from app.services.lot_queries import build_lot_query
from app.services.map_queries import build_bin_meta_query, build_die_map_query
from app.services.wat_queries import build_wat_detail_query, build_wat_lots_query
from app.services.yield_queries import build_product_id_where

# Oracle SQL reserved words (V$RESERVED_WORDS, the RESERVED='Y' subset).
_SQL_RESERVED = """
    access add all alter and any as asc audit between by char check cluster
    column comment compress connect create current date decimal default delete
    desc distinct drop else exclusive exists file float for from grant group
    having identified immediate in increment index initial insert integer
    intersect into is level like lock long maxextents minus mlslabel mode
    modify noaudit nocompress not nowait null number of offline on online
    option or order pctfree prior public raw rename resource revoke row rowid
    rownum rows select session set share size smallint start successful synonym
    sysdate table then to trigger uid union unique update user validate values
    varchar varchar2 view whenever where with
"""

# PL/SQL keywords. The parser rejects these as bind names too — END is the one
# that bit us, and it is absent from the SQL list above.
_PLSQL_KEYWORDS = """
    begin body case close constant cursor declare end exception exit fetch
    function goto if loop open others out package pragma procedure raise record
    return subtype type when while
"""

# A bind name equal to any of these raises ORA-01745.
ORACLE_RESERVED = frozenset((_SQL_RESERVED + _PLSQL_KEYWORDS).split())

SERVICES = pathlib.Path(__file__).resolve().parent.parent / "app" / "services"

# `:name` inside a SQL string. Digits are excluded at the first character so
# Python slices (lst[:3]) never match.
BIND_TOKEN = re.compile(r":([A-Za-z_]\w*)")


def _sql_string_literals(path: pathlib.Path) -> list[str]:
    """Every string constant in the module EXCEPT docstrings — prose about
    reserved words must not be mistaken for a bind name."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def _query_modules() -> list[pathlib.Path]:
    return sorted(SERVICES.glob("*_queries.py"))


def test_query_modules_are_actually_found():
    """A glob that silently matches nothing would make the scan vacuously pass."""
    assert len(_query_modules()) >= 4


@pytest.mark.parametrize("path", _query_modules(), ids=lambda p: p.name)
def test_literal_bind_names_avoid_oracle_reserved_words(path):
    found = {
        name
        for literal in _sql_string_literals(path)
        for name in BIND_TOKEN.findall(literal)
    }
    offenders = sorted(n for n in found if n.lower() in ORACLE_RESERVED)
    assert not offenders, (
        f"{path.name} binds Oracle reserved words {offenders} — oracledb raises "
        f"ORA-01745 at execute time. Suffix them (e.g. start -> start_dt)."
    )


# Builders that return (sql, binds) and need no database connection.
BUILDER_CASES = [
    ("wat_lots", lambda: build_wat_lots_query("P1", date(2026, 1, 1), date(2026, 2, 1))),
    ("wat_lots_wildcard", lambda: build_wat_lots_query("P%", date(2026, 1, 1), date(2026, 2, 1))),
    ("wat_detail", lambda: build_wat_detail_query("P1", "LOT-1")),
    ("lot_cp", lambda: build_lot_query("CP", ["P1", "P%"], "2026-01", "2026-03", ["CP", "CP1"])),
    ("die_map", lambda: build_die_map_query(["LOT-1", "LOT-2"], ["CP"])),
    ("bin_meta", lambda: build_bin_meta_query(["LOT-1", "LOT-2"], ["CP"])),
    ("product_id_where", lambda: build_product_id_where(["P1", "P%"])),
]


@pytest.mark.parametrize("name,build", BUILDER_CASES, ids=[c[0] for c in BUILDER_CASES])
def test_generated_bind_names_avoid_oracle_reserved_words(name, build):
    result = build()
    binds = result[1] if isinstance(result, tuple) else result
    assert binds, f"{name} produced no binds — the case is not exercising anything"
    offenders = sorted(k for k in binds if k.lower() in ORACLE_RESERVED)
    assert not offenders, (
        f"{name} binds Oracle reserved words {offenders} — oracledb raises "
        f"ORA-01745 at execute time."
    )


def test_reserved_word_detector_catches_a_known_offender():
    """The scan is only worth having if it would have caught the real bug."""
    broken = "SELECT * FROM T WHERE D >= :start AND D < :end"
    found = sorted(n for n in BIND_TOKEN.findall(broken) if n.lower() in ORACLE_RESERVED)
    assert found == ["end", "start"]
