from app.services.summary_service import build_summary


def test_build_summary_returns_rows_for_all_products():
    resp = build_summary(months=6, process="all")
    assert resp["period"]["months"] == 6
    assert resp["rows"]
    sample = resp["rows"][0]
    for key in ["nickname", "display_name", "process", "latest_yield",
                "avg_yield_6m", "delta", "sparkline", "warnings"]:
        assert key in sample


def test_build_summary_filters_by_process():
    resp = build_summary(months=6, process="CP")
    assert all(r["process"] == "CP" for r in resp["rows"])


def test_build_summary_computes_delta_and_sparkline():
    resp = build_summary(months=6, process="CP")
    row = resp["rows"][0]
    assert row["delta"] == round(row["latest_yield"] - row["avg_yield_6m"], 2)
    assert len(row["sparkline"]) >= 1
