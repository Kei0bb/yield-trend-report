import pandas as pd

from app.services.wat_service import SCATTER_KINDS, build_scatter_pairs

PAIR = {
    "label": "Core RVT",
    "vth_n": "VTHN", "vth_p": "VTHP",
    "idsat_n": "IDSATN", "idsat_p": "IDSATP",
}

STATS = {
    "VTHN": {"unit": "V", "spec_low": 0.38, "spec_high": 0.52},
    "VTHP": {"unit": "V", "spec_low": -0.52, "spec_high": -0.38},
    "IDSATN": {"unit": "uA/um", "spec_low": 500.0, "spec_high": 700.0},
    "IDSATP": {"unit": "uA/um", "spec_low": 220.0, "spec_high": 320.0},
}


def _df(rows):
    return pd.DataFrame(rows, columns=["wafer_id", "site_no", "item_name", "meas_data"])


def _full_df():
    rows = []
    for wafer in (1, 2):
        for site in (1, 2):
            rows.append([wafer, site, "VTHN", 0.45])
            rows.append([wafer, site, "VTHP", -0.45])
            rows.append([wafer, site, "IDSATN", 600.0])
            rows.append([wafer, site, "IDSATP", 270.0])
    return _df(rows)


def test_returns_four_plots_in_fixed_order():
    result = build_scatter_pairs(_full_df(), [PAIR], STATS)
    assert len(result) == 1
    assert result[0]["label"] == "Core RVT"
    assert [p["kind"] for p in result[0]["plots"]] == [k for k, _, _ in SCATTER_KINDS]
    assert [p["kind"] for p in result[0]["plots"]] == [
        "vth_np", "idsat_np", "ion_vt_n", "ion_vt_p",
    ]


def test_points_are_paired_per_wafer_and_site():
    plots = build_scatter_pairs(_full_df(), [PAIR], STATS)[0]["plots"]
    vth_np = plots[0]
    assert len(vth_np["points"]) == 4          # 2 wafers x 2 sites
    pt = vth_np["points"][0]
    assert set(pt) == {"wafer_id", "site_no", "x", "y"}
    assert pt["x"] == 0.45 and pt["y"] == -0.45


def test_site_with_one_side_missing_is_dropped():
    rows = [
        [1, 1, "VTHN", 0.45], [1, 1, "VTHP", -0.45],
        [1, 2, "VTHN", 0.46],                      # no VTHP at site 2
    ]
    plots = build_scatter_pairs(_df(rows), [PAIR], STATS)[0]["plots"]
    assert len(plots[0]["points"]) == 1
    assert plots[0]["points"][0]["site_no"] == 1


def test_plot_carries_item_names_units_and_spec_ranges():
    plots = build_scatter_pairs(_full_df(), [PAIR], STATS)[0]["plots"]
    ion_vt_n = plots[2]
    assert ion_vt_n["x_item"] == "VTHN" and ion_vt_n["y_item"] == "IDSATN"
    assert ion_vt_n["x_unit"] == "V" and ion_vt_n["y_unit"] == "uA/um"
    assert ion_vt_n["x_spec"] == [0.38, 0.52]
    assert ion_vt_n["y_spec"] == [500.0, 700.0]


def test_missing_item_yields_an_empty_plot_not_a_failure():
    rows = [[1, 1, "VTHN", 0.45], [1, 1, "IDSATN", 600.0]]
    plots = build_scatter_pairs(_df(rows), [PAIR], {"VTHN": STATS["VTHN"],
                                                    "IDSATN": STATS["IDSATN"]})[0]["plots"]
    by_kind = {p["kind"]: p for p in plots}
    assert by_kind["vth_np"]["points"] == []      # VTHP absent
    assert len(by_kind["ion_vt_n"]["points"]) == 1
    assert by_kind["vth_np"]["x_spec"] == [0.38, 0.52]
    assert by_kind["vth_np"]["y_spec"] == [None, None]


def test_no_pairs_configured_returns_empty_list():
    assert build_scatter_pairs(_full_df(), [], STATS) == []


def test_empty_dataframe_returns_pairs_with_empty_plots():
    empty = _df([])
    result = build_scatter_pairs(empty, [PAIR], STATS)
    assert len(result) == 1
    assert all(p["points"] == [] for p in result[0]["plots"])


def test_null_measurement_drops_the_point():
    rows = [
        [1, 1, "VTHN", 0.45], [1, 1, "VTHP", None],
        [1, 2, "VTHN", 0.46], [1, 2, "VTHP", -0.46],
    ]
    plots = build_scatter_pairs(_df(rows), [PAIR], STATS)[0]["plots"]
    assert len(plots[0]["points"]) == 1
    assert plots[0]["points"][0]["site_no"] == 2
