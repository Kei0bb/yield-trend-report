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


def test_bin_pct_denominator_is_substrate_aware_not_wafer_id_alone():
    """WAFER_ID is only the per-substrate slot number, so it repeats across the
    multiple substrates rolled into one ISO-week lot_id. The denominator must
    dedupe by SUBSTRATE_ID + WAFER_ID, not WAFER_ID alone — otherwise same-numbered
    wafers on different substrates collapse into one, shrinking the denominator
    and inflating bin% past 100%.

    1 lot, 2 substrates, each with ONE wafer both labeled wafer_id="1",
    gross_die=1000 each (total gross = 2000). binA fails 100 on each substrate
    (total fail = 200) → 200/2000 = 10.0% (NOT 200/1000 = 20.0%).
    """
    cols = ["lot_id", "substrate_id", "wafer_id", "yield_pct", "gross_die",
             "raw_bin_code", "bin_name", "bin_code", "bin_fail_count"]
    df = pd.DataFrame([
        ("2026W01", "S1", "1", 90.0, 1000, 100, "binA", "binA", 100),
        ("2026W01", "S2", "1", 90.0, 1000, 100, "binA", "binA", 100),
    ], columns=cols)
    out = aggregate_lot_data(df, target_lots=["2026W01"])
    assert out.fail_bins["binA"] == [10.0]


def test_lot_without_fail_bins_still_counts_toward_yield_and_denominator():
    """SLT outer-joins its bin table so a zero-fail lot arrives with a null
    bin_code. It must still average into the week's yield and contribute its
    gross die, or bin% is computed against too small a denominator.

    2 assembly lots in one week, gross 1000 each → denominator 2000.
    Only the first has a fail bin: 20/2000 = 1.0%.
    """
    cols = ["lot_id", "substrate_id", "wafer_id", "yield_pct", "gross_die",
            "bin_code", "bin_fail_count"]
    df = pd.DataFrame(
        [
            ("2026W01", "ASSY-A", "0", 98.0, 1000, "Open", 20),
            ("2026W01", "ASSY-B", "0", 100.0, 1000, None, None),
        ],
        columns=cols,
    )
    out = aggregate_lot_data(df, target_lots=["2026W01"])
    assert out.yield_avg == [99.0]
    assert out.fail_bins["Open"] == [1.0]
