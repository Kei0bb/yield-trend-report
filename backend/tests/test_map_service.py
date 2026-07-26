from app.services.map_service import clear_map_cache, get_wafer_maps
from app.services.map_queries import BIN_META_COLUMNS, DIE_COLUMNS
from app.services.mock_data import mock_bin_meta_dataframe, mock_die_dataframe


def setup_function():
    clear_map_cache()


def test_mock_die_dataframe_is_deterministic_and_circular():
    df1 = mock_die_dataframe("LOT-A", "CP")
    df2 = mock_die_dataframe("LOT-A", "CP")
    assert list(df1.columns) == DIE_COLUMNS
    assert df1.equals(df2)                       # same seed → identical
    assert df1["wafer_id"].nunique() >= 3        # multiple wafers per lot
    one = df1[df1["wafer_id"] == df1["wafer_id"].iloc[0]]
    assert 150 <= len(one) <= 260                # ~200 die circle
    assert (one["bin_code"] == 1).sum() > len(one) * 0.5


def test_mock_bin_meta_dataframe_is_deterministic():
    df1 = mock_bin_meta_dataframe("LOT-A", "CP")
    df2 = mock_bin_meta_dataframe("LOT-A", "CP")
    assert list(df1.columns) == BIN_META_COLUMNS
    assert df1.equals(df2)
    quality_by_code = dict(zip(df1["bin_code"], df1["bin_quality"]))
    assert quality_by_code[1] == "PASS"
    assert quality_by_code[7] == "FAIL"
    assert quality_by_code[13] == "FAIL"
    assert quality_by_code[2] == "FAIL"


def test_get_wafer_maps_mock_shape_and_legend():
    resp = get_wafer_maps("Product-A", "CP", ["LOT-A", "LOT-B"])
    assert resp.wafers, "wafers should not be empty in mock mode"
    w = resp.wafers[0]
    assert len(w.x) == len(w.y) == len(w.bin) > 0
    lot_ids = {wf.lot_id for wf in resp.wafers}
    assert lot_ids == {"LOT-A", "LOT-B"}
    # legend: fail bins only, count-descending, labels non-empty
    counts = [item.count for item in resp.legend]
    assert counts == sorted(counts, reverse=True)
    assert all(item.label for item in resp.legend)
    assert all(item.bin_code not in resp.pass_bin_codes for item in resp.legend)
    assert resp.pass_bin_codes == [1], "mock must mark bin 1 as the pass bin"


def test_get_wafer_maps_rows_follow_requested_lot_order():
    """Grid rows must follow the caller's lot order (UI sends lot_date desc),
    not alphabetical SUBSTRATE_ID order."""
    requested = ["LOT-B", "LOT-A"]
    resp = get_wafer_maps("Product-A", "CP", requested)
    seen: list[str] = []
    for wf in resp.wafers:
        if wf.lot_id not in seen:
            seen.append(wf.lot_id)
    assert seen == requested


def test_get_wafer_maps_caches_per_lot(monkeypatch):
    calls = []
    import app.services.map_service as ms
    real = ms._load_die_df

    def spy(nickname, process, lot_id, process_values):
        calls.append(lot_id)
        return real(nickname, process, lot_id, process_values)

    monkeypatch.setattr(ms, "_load_die_df", spy)
    get_wafer_maps("Product-A", "CP", ["LOT-A", "LOT-B"])
    get_wafer_maps("Product-A", "CP", ["LOT-B"])   # fully cached — no new call
    assert calls.count("LOT-B") == 1
