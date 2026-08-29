"""The SLT query outer-joins its bin table, so a lot with zero fail bins arrives
as a header row carrying no bin at all. Bin-group mapping must survive that."""

import pandas as pd

from app.services import bin_mapping
from app.services.bin_mapping import apply_bin_groups


def _df():
    return pd.DataFrame(
        {
            "raw_bin_code": [3, None, 99],
            "bin_name": ["RawOpen", None, "RawOther"],
        }
    )


def test_null_raw_bin_code_does_not_raise_and_stays_null(monkeypatch):
    monkeypatch.setattr(
        bin_mapping, "load_bin_mapping", lambda _g: {"*": {3: "Open", 5: "Short"}}
    )
    out = apply_bin_groups(_df(), bin_group="main", process="SLT")

    assert out["bin_code"].iloc[0] == "Open"        # mapped
    assert pd.isna(out["bin_code"].iloc[1])          # no bin at all — stays null
    assert out["bin_code"].iloc[2] == "RawOther"     # unmapped → DB bin name


def test_null_raw_bin_code_survives_an_empty_mapping(monkeypatch):
    monkeypatch.setattr(bin_mapping, "load_bin_mapping", lambda _g: {})
    out = apply_bin_groups(_df(), bin_group="missing", process="SLT")

    assert out["bin_code"].tolist()[0] == "RawOpen"
    assert pd.isna(out["bin_code"].iloc[1])
