import pandas as pd

from app.services.mock_data import (
    MOCK_WAT_FLAVORS, mock_wat_dataframe, mock_wat_lots,
)

WAT_DETAIL_COLUMNS = [
    "wafer_id", "site_no", "item_name", "item_unit",
    "spec_low", "spec_high", "meas_data", "start_time",
]


def test_mock_wat_lots_shape_and_determinism():
    a = mock_wat_lots("P12345-A", 3)
    b = mock_wat_lots("P12345-A", 3)
    assert list(a.columns) == ["lot_id", "last_measured", "wafer_count"]
    assert a.equals(b)
    assert len(a) >= 3
    # oldest first — the router is what reverses
    assert list(a["last_measured"]) == sorted(a["last_measured"])


def test_mock_wat_lots_differ_per_product():
    a = mock_wat_lots("P12345-A", 3)
    b = mock_wat_lots("P12345-B", 3)
    assert set(a["lot_id"]) != set(b["lot_id"])


def test_mock_wat_dataframe_shape_and_determinism():
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[0]
    a = mock_wat_dataframe("P12345-A", lot)
    b = mock_wat_dataframe("P12345-A", lot)
    assert list(a.columns) == WAT_DETAIL_COLUMNS
    assert a.equals(b)
    assert a["wafer_id"].nunique() == 25
    assert a["site_no"].nunique() == 9


def test_mock_wat_dataframe_covers_every_flavor():
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[0]
    df = mock_wat_dataframe("P12345-A", lot)
    names = set(df["item_name"])
    for flavor in MOCK_WAT_FLAVORS:
        for prefix in ("VTHN", "VTHP", "IDSATN", "IDSATP"):
            assert f"{prefix}_{flavor}" in names


def test_mock_wat_dataframe_has_spec_and_units():
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[0]
    df = mock_wat_dataframe("P12345-A", lot)
    vth = df[df["item_name"] == "VTHN_RVT"]
    assert vth["item_unit"].iloc[0] == "V"
    # spec is constant within an item
    assert vth["spec_low"].nunique() == 1
    assert vth["spec_high"].nunique() == 1


def test_mock_wat_dataframe_contains_out_of_spec_and_low_cpk():
    """Mock must exercise the red/yellow rendering paths without a real DB."""
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[0]
    df = mock_wat_dataframe("P12345-A", lot)
    oos = df[(df["meas_data"] < df["spec_low"]) | (df["meas_data"] > df["spec_high"])]
    assert not oos.empty, "mock must include out-of-spec measurements"


def test_mock_wat_dataframe_unknown_lot_is_empty():
    df = mock_wat_dataframe("P12345-A", "__no_such_lot__")
    assert df.empty
    assert list(df.columns) == WAT_DETAIL_COLUMNS
