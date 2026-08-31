"""SLT reads the FT schema, whose bin codes are unrelated to the CP-oriented
bin_mappings CSVs, so its fail bins must come through as the DB's own BIN_NAME."""

import pandas as pd
import pytest

from app.services import yield_service
from app.services.yield_queries import COMMON_COLUMNS
from app.services.yield_service import get_yield_data_merged


def _df(weeks):
    return pd.DataFrame(
        [
            (weeks[0], "0", 98.0, 1000, 3, "FT_OPEN", 20, "ASSY-A"),
            (weeks[1], "0", 97.0, 1000, 5, "FT_SHORT", 30, "ASSY-B"),
        ],
        columns=COMMON_COLUMNS,
    )


@pytest.fixture
def db_mode(monkeypatch):
    """Force the real-DB branch and capture the bin_group handed to the mapper."""
    monkeypatch.setattr(yield_service.settings, "USE_MOCK_DATA", False)
    monkeypatch.setattr(yield_service, "resolve_product_ids", lambda n, p: ["P1"])
    monkeypatch.setattr(yield_service, "resolve_process_filter", lambda n, p: ["X"])
    monkeypatch.setattr(yield_service, "resolve_bin_group", lambda n, p: "main")

    seen: dict = {}
    real_apply = yield_service.apply_bin_groups

    def spy(df, bin_group, process):
        seen["bin_group"] = bin_group
        # A mapping that WOULD rewrite these codes if it were consulted.
        return real_apply(df, bin_group=bin_group, process=process)

    monkeypatch.setattr(yield_service, "apply_bin_groups", spy)
    return seen


def _run(monkeypatch, process):
    weeks = ["W1", "W2"]
    monkeypatch.setattr(
        yield_service, "query_yield_data",
        lambda *a, **k: _df(weeks),
    )
    monkeypatch.setattr(yield_service, "latest_iso_weeks", lambda *a, **k: weeks)
    return get_yield_data_merged(["nick"], "2026-03", "2026-08", process)


def test_slt_skips_the_bin_mapping_csv(db_mode, monkeypatch):
    out = _run(monkeypatch, "SLT")
    assert db_mode["bin_group"] == "", "SLT must not be handed a mapping file"
    assert sorted(out.fail_bins) == ["FT_OPEN", "FT_SHORT"], "raw DB BIN_NAME expected"


@pytest.mark.parametrize("process", ["CP", "FT"])
def test_cp_and_ft_still_use_their_bin_group(db_mode, monkeypatch, process):
    _run(monkeypatch, process)
    assert db_mode["bin_group"] == "main"
