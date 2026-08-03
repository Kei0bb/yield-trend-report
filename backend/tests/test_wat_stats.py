import math

import pandas as pd
import pytest

from app.services.wat_service import (
    classify_status, compute_cpk, compute_item_stats,
    count_out_of_spec, resolve_spec,
)


# --- compute_cpk -----------------------------------------------------------

def test_cpk_two_sided_uses_the_worse_side():
    # mean 0.45, sigma 0.02 → upper (0.52-0.45)/0.06 = 1.167
    #                         lower (0.45-0.38)/0.06 = 1.167
    cpk, state = compute_cpk(0.45, 0.02, 0.38, 0.52, n=100, oos_count=0)
    assert state == "value"
    assert cpk == pytest.approx(1.1667, rel=1e-3)


def test_cpk_two_sided_picks_the_nearer_limit():
    cpk, state = compute_cpk(0.50, 0.02, 0.38, 0.52, n=100, oos_count=0)
    assert state == "value"
    assert cpk == pytest.approx((0.52 - 0.50) / 0.06, rel=1e-6)


def test_cpk_upper_only():
    cpk, state = compute_cpk(10.0, 1.0, None, 16.0, n=100, oos_count=0)
    assert state == "value"
    assert cpk == pytest.approx(2.0)


def test_cpk_lower_only():
    cpk, state = compute_cpk(10.0, 1.0, 4.0, None, n=100, oos_count=0)
    assert state == "value"
    assert cpk == pytest.approx(2.0)


def test_cpk_no_spec_is_undefined():
    assert compute_cpk(1.0, 0.1, None, None, n=100, oos_count=0) == (None, "undefined")


def test_cpk_zero_sigma_in_spec_is_infinite():
    assert compute_cpk(0.45, 0.0, 0.38, 0.52, n=100, oos_count=0) == (None, "infinite")


def test_cpk_zero_sigma_out_of_spec_is_undefined():
    assert compute_cpk(0.90, 0.0, 0.38, 0.52, n=100, oos_count=5) == (None, "undefined")


def test_cpk_needs_at_least_two_samples():
    assert compute_cpk(0.45, 0.0, 0.38, 0.52, n=1, oos_count=0) == (None, "undefined")


def test_cpk_nan_sigma_is_undefined():
    assert compute_cpk(0.45, float("nan"), 0.38, 0.52, n=100, oos_count=0) == (None, "undefined")


# --- classify_status -------------------------------------------------------

def test_status_red_when_any_measurement_out_of_spec():
    assert classify_status(2.5, "value", oos_count=1) == "red"


def test_status_red_when_cpk_below_one():
    assert classify_status(0.99, "value", oos_count=0) == "red"


def test_status_boundary_cpk_exactly_one_is_yellow_not_red():
    assert classify_status(1.00, "value", oos_count=0) == "yellow"


def test_status_boundary_cpk_exactly_133_is_ok_not_yellow():
    assert classify_status(1.33, "value", oos_count=0) == "ok"


def test_status_yellow_between_thresholds():
    assert classify_status(1.32, "value", oos_count=0) == "yellow"


def test_status_gray_when_cpk_undefined():
    assert classify_status(None, "undefined", oos_count=0) == "gray"


def test_status_out_of_spec_beats_undefined_cpk():
    """n<2 with a failing measurement must read red, not gray."""
    assert classify_status(None, "undefined", oos_count=1) == "red"


def test_status_infinite_cpk_is_ok():
    assert classify_status(None, "infinite", oos_count=0) == "ok"


# --- count_out_of_spec -----------------------------------------------------

def test_out_of_spec_excludes_values_exactly_on_the_limit():
    s = pd.Series([0.38, 0.52, 0.45])
    assert count_out_of_spec(s, 0.38, 0.52) == 0


def test_out_of_spec_counts_both_tails():
    s = pd.Series([0.37, 0.45, 0.53])
    assert count_out_of_spec(s, 0.38, 0.52) == 2


def test_out_of_spec_one_sided_uses_only_the_present_limit():
    s = pd.Series([0.01, 0.45, 99.0])
    assert count_out_of_spec(s, None, 0.52) == 1
    assert count_out_of_spec(s, 0.38, None) == 1


def test_out_of_spec_without_spec_is_zero():
    assert count_out_of_spec(pd.Series([1.0, 2.0]), None, None) == 0


# --- resolve_spec ----------------------------------------------------------

def test_resolve_spec_returns_the_single_value():
    assert resolve_spec(pd.Series([0.38, 0.38, 0.38]), "VTH_N") == 0.38


def test_resolve_spec_ignores_nulls():
    assert resolve_spec(pd.Series([None, 0.38, None]), "VTH_N") == 0.38


def test_resolve_spec_all_null_is_none():
    assert resolve_spec(pd.Series([None, None]), "VTH_N") is None


def test_resolve_spec_takes_the_mode_and_warns_on_mixed(caplog):
    s = pd.Series([0.38, 0.38, 0.40])
    with caplog.at_level("WARNING"):
        assert resolve_spec(s, "VTH_N") == 0.38
    assert "VTH_N" in caplog.text


def test_resolve_spec_tie_breaks_on_ascending_sort():
    s = pd.Series([0.40, 0.38])
    assert resolve_spec(s, "VTH_N") == 0.38


# --- compute_item_stats ----------------------------------------------------

def _group(values, spec_low=0.38, spec_high=0.52, unit="V"):
    return pd.DataFrame({
        "wafer_id": [1] * len(values),
        "site_no": list(range(1, len(values) + 1)),
        "item_unit": [unit] * len(values),
        "spec_low": [spec_low] * len(values),
        "spec_high": [spec_high] * len(values),
        "meas_data": values,
    })


def test_item_stats_basic_fields():
    st = compute_item_stats(_group([0.44, 0.45, 0.46]), "VTH_N")
    assert st["item_name"] == "VTH_N"
    assert st["unit"] == "V"
    assert st["n"] == 3
    assert st["mean"] == pytest.approx(0.45)
    assert st["min"] == pytest.approx(0.44)
    assert st["max"] == pytest.approx(0.46)
    assert st["spec_low"] == pytest.approx(0.38)
    assert st["spec_high"] == pytest.approx(0.52)


def test_item_stats_uses_sample_stddev_ddof_1():
    st = compute_item_stats(_group([1.0, 2.0, 3.0], spec_low=None, spec_high=None), "X")
    assert st["sigma"] == pytest.approx(1.0)   # ddof=1, not 0.8165


def test_item_stats_drops_null_measurements_from_n():
    st = compute_item_stats(_group([0.44, None, 0.46]), "VTH_N")
    assert st["n"] == 2


def test_item_stats_all_null_yields_zero_n_and_gray():
    st = compute_item_stats(_group([None, None]), "VTH_N")
    assert st["n"] == 0
    assert st["mean"] is None
    assert st["cpk_state"] == "undefined"
    assert st["status"] == "gray"


def test_item_stats_reports_out_of_spec_count_and_pct():
    st = compute_item_stats(_group([0.30, 0.45, 0.45, 0.45]), "VTH_N")
    assert st["oos_count"] == 1
    assert st["oos_pct"] == pytest.approx(25.0)


def test_item_stats_wafer_series_is_ordered_and_sized():
    df = pd.DataFrame({
        "wafer_id": [2, 2, 1, 1],
        "site_no": [1, 2, 1, 2],
        "item_unit": ["V"] * 4,
        "spec_low": [0.38] * 4,
        "spec_high": [0.52] * 4,
        "meas_data": [0.46, 0.46, 0.44, 0.44],
    })
    st = compute_item_stats(df, "VTH_N")
    assert [w["wafer_id"] for w in st["wafer_series"]] == [1, 2]
    assert st["wafer_series"][0]["mean"] == pytest.approx(0.44)
    assert st["wafer_series"][0]["n"] == 2


def test_item_stats_wafer_sigma_is_none_when_single_site():
    df = pd.DataFrame({
        "wafer_id": [1],
        "site_no": [1],
        "item_unit": ["V"],
        "spec_low": [0.38],
        "spec_high": [0.52],
        "meas_data": [0.45],
    })
    st = compute_item_stats(df, "VTH_N")
    assert st["wafer_series"][0]["sigma"] is None


def test_item_stats_has_no_nan_in_json_facing_fields():
    """NaN is not valid JSON — every numeric field must be a float or None."""
    st = compute_item_stats(_group([None, None]), "VTH_N")
    for key in ("mean", "sigma", "min", "max", "cpk"):
        assert st[key] is None or not math.isnan(st[key])
