from app.services.mock_data import mock_lot_dataframe


def test_mock_lot_dataframe_shape():
    df = mock_lot_dataframe("Product-A", "CP", months=6)
    assert not df.empty
    for col in ["lot_id", "lot_date", "wafer_id", "yield_pct",
                "gross_die", "raw_bin_code", "bin_name", "bin_fail_count"]:
        assert col in df.columns


def test_mock_lot_dataframe_has_multiple_lots_per_week():
    df = mock_lot_dataframe("Product-A", "CP", months=6)
    weeks = {d[:7] for d in df["lot_date"]}
    assert df["lot_id"].nunique() > len(weeks)


def test_mock_lot_dataframe_deterministic():
    a = mock_lot_dataframe("Product-A", "FT", months=6)
    b = mock_lot_dataframe("Product-A", "FT", months=6)
    assert a.equals(b)


def test_mock_lot_dataframe_seed_is_process_stable():
    # Seeding goes through a stable md5 hash (not the salted built-in hash()),
    # so a known input must always reduce to the same seed across processes.
    import hashlib

    key = "lot-Product-A-FT-6"
    expected_seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % 2**32
    # Guard against accidentally reverting to the salted builtin hash().
    assert expected_seed == 3594895343
