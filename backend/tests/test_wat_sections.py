import pandas as pd
import pytest

from app.models.schemas import WatItemStats
from app.services.wat_pdf_common import paginate_table, section_label, table_rows
from app.services.wat_service import (
    SECTION_ORDER, _item_core, classify_section, compute_item_stats,
    get_wat_summary, item_sort_key,
)
from app.services.mock_data import mock_wat_lots
from app.services.wat_trend_service import build_lot_series, _lot_dates


def _group(values, spec_low=0.0, spec_high=1.0, name="X"):
    return pd.DataFrame({
        "lot_id": ["LOT-1"] * len(values),
        "wafer_id": [1, 1, 2, 2, 3, 3][:len(values)],
        "site_no": list(range(1, len(values) + 1)),
        "item_name": [name] * len(values),
        "item_unit": ["V"] * len(values),
        "spec_low": [spec_low] * len(values),
        "spec_high": [spec_high] * len(values),
        "meas_data": values,
        "start_time": ["2026-09-01"] * len(values),
    })


@pytest.mark.parametrize("name,section", [
    ("Isat_N_RVT", "Isat"),
    ("Vtl_P_LVT", "Vtl"),
    ("Rc_NDIFF", "Rc"),
    ("Con_VIA_CHAIN", "Con"),
    ("ISAT_N_RVT", "Isat"),     # case-insensitive
    ("vtl_x", "Vtl"),
    ("RS_POLY", "Others"),
    ("Isat", "Others"),         # the prefix includes the underscore
    ("XIsat_N", "Others"),      # prefix, not substring
    ("", "Others"),
])
def test_classify_section(name, section):
    assert classify_section(name) == section


def test_item_sort_key_orders_by_section_then_name():
    names = ["RS_POLY", "Con_B", "Vtl_A", "Isat_Z", "Rc_A", "Isat_A", "CAP"]
    assert sorted(names, key=item_sort_key) == [
        "Isat_A", "Isat_Z", "Vtl_A", "Rc_A", "Con_B", "CAP", "RS_POLY",
    ]
    assert SECTION_ORDER[-1] == "Others"


def test_others_item_keeps_descriptive_stats_but_no_sigma_cpk_oos_or_judgement():
    # 1.5 is out of spec: a judged item would be red with oos_count=1.
    core = _item_core(_group([0.2, 0.5, 1.5]), "GATE_OX_TOX", 0.0, 1.0)
    assert core["section"] == "Others"
    assert core["n"] == 3
    assert core["mean"] == pytest.approx(0.7333333)
    assert core["min"] == 0.2 and core["max"] == 1.5
    assert core["spec_low"] == 0.0 and core["spec_high"] == 1.0
    assert core["sigma"] is None
    assert core["cpk"] is None and core["cpk_state"] == "undefined"
    assert core["oos_count"] == 0 and core["oos_pct"] == 0.0
    assert core["status"] == "excluded"


def test_judged_section_item_with_same_data_is_red():
    core = _item_core(_group([0.2, 0.5, 1.5]), "Vtl_N", 0.0, 1.0)
    assert core["section"] == "Vtl"
    assert core["sigma"] is not None
    assert core["oos_count"] == 1
    assert core["status"] == "red"


def test_others_wafer_series_has_no_sigma():
    st = compute_item_stats(_group([0.4, 0.5, 0.6, 0.5]), "RS_POLY")
    assert st["wafer_series"]
    assert all(w["sigma"] is None for w in st["wafer_series"])
    assert all(w["mean"] is not None for w in st["wafer_series"])


def test_others_lot_series_has_no_sigma_and_excluded_status():
    df = _group([0.4, 0.5, 0.6, 5.0])
    series = build_lot_series(df, "RS_POLY", 0.0, 1.0, _lot_dates(df))
    assert [p["status"] for p in series] == ["excluded"]
    assert series[0]["sigma"] is None


def test_mock_summary_has_every_section_and_no_flagged_others():
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    res = get_wat_summary("product_a", "P12345-A", lot)
    assert {i.section for i in res.items} == set(SECTION_ORDER)
    assert all(i.status == "excluded" for i in res.items if i.section == "Others")
    assert all(i.status != "excluded" for i in res.items if i.section != "Others")


# --- PDF table rows / pagination --------------------------------------------

def _item(name: str) -> WatItemStats:
    return WatItemStats(
        item_name=name, section=classify_section(name), unit="V",
        n=1, cpk_state="undefined", oos_count=0, oos_pct=0.0,
        status="gray", wafer_series=[],
    )


def test_table_rows_put_a_heading_before_each_section():
    items = [_item(n) for n in ("Isat_A", "Isat_B", "Rc_A", "OTHER")]
    rows = table_rows(items)
    assert [(r.section, r.count, r.item.item_name if r.item else None) for r in rows] == [
        ("Isat", 2, None), ("Isat", 0, "Isat_A"), ("Isat", 0, "Isat_B"),
        ("Rc", 1, None), ("Rc", 0, "Rc_A"),
        ("Others", 1, None), ("Others", 0, "OTHER"),
    ]


def test_paginate_never_leaves_a_heading_last_on_a_page():
    # Rows: [Isat-h, Isat_A, Isat_B, Rc-h, Rc_A]. With 4 per page the Rc
    # heading would be row 4 — the last slot — so it moves to page 2.
    items = [_item(n) for n in ("Isat_A", "Isat_B", "Rc_A")]
    pages = paginate_table(items, 4)
    assert [len(p) for p in pages] == [3, 2]
    assert pages[1][0].item is None and pages[1][0].section == "Rc"


def test_paginate_empty_is_one_empty_page():
    assert paginate_table([], 10) == [[]]


def test_section_label_notes_others_are_not_evaluated():
    assert section_label("Vtl", 1) == "Vtl  ·  1 item"
    assert "not evaluated" in section_label("Others", 3)
