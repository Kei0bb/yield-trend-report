import pandas as pd

from app.services.yield_aggregator import aggregate_lot_data


def _df(rows):
    cols = ["lot_id", "wafer_id", "yield_pct", "gross_die",
            "raw_bin_code", "bin_name", "bin_code", "bin_fail_count"]
    return pd.DataFrame(rows, columns=cols)


def test_bin_pct_denominator_is_total_lot_gross_not_per_bin():
    """bin% must use the lot's total gross die (each wafer counted once),
    NOT the per-(lot,bin) row sum of gross_die.

    1 lot, 2 wafers, EFFECTIVE_NUM=1000 each → total gross = 2000.
      binA fails: W1=10, W2=30 → 40/2000 = 2.0%
      binB fails: W1=20        → 20/2000 = 1.0%
    """
    df = _df([
        ("2026W01", "W1", 99.0, 1000, 100, "binA", "binA", 10),
        ("2026W01", "W1", 99.0, 1000, 200, "binB", "binB", 20),
        ("2026W01", "W2", 97.0, 1000, 100, "binA", "binA", 30),
    ])
    out = aggregate_lot_data(df, target_lots=["2026W01"])
    assert out.fail_bins["binA"] == [2.0]
    assert out.fail_bins["binB"] == [1.0]


def test_bin_pct_not_deflated_by_mapped_group_collision():
    """When several raw bins collapse into one mapped group on the same wafer,
    the wafer's gross_die must still count once (not once per raw bin).

    1 lot, 1 wafer, gross=1000. Raw bins 100/101/102 → group 'GroupX',
    fails 10+20+30 = 60 → 60/1000 = 6.0% (not 2.0%).
    """
    df = _df([
        ("2026W01", "W1", 94.0, 1000, 100, "GroupX", "GroupX", 10),
        ("2026W01", "W1", 94.0, 1000, 101, "GroupX", "GroupX", 20),
        ("2026W01", "W1", 94.0, 1000, 102, "GroupX", "GroupX", 30),
    ])
    out = aggregate_lot_data(df, target_lots=["2026W01"])
    assert out.fail_bins["GroupX"] == [6.0]
