from app.services.anomaly_service import load_anomaly_config, resolve_config


def test_load_returns_defaults_and_overrides():
    cfg = load_anomaly_config()
    assert cfg["defaults"]["yield_drop"]["threshold_pct"] == 3.0
    assert cfg["defaults"]["bin_surge"]["multiplier"] == 2.0
    assert "Product-A" in cfg["overrides"]


def test_resolve_without_override_returns_defaults():
    cfg = {"defaults": {"yield_drop": {"threshold_pct": 3.0, "min_lots": 3}},
           "overrides": {}}
    resolved = resolve_config("Unknown", cfg)
    assert resolved["yield_drop"]["threshold_pct"] == 3.0


def test_resolve_deep_merges_override():
    cfg = {
        "defaults": {"yield_drop": {"threshold_pct": 3.0, "min_lots": 3},
                     "bin_surge": {"multiplier": 2.0, "min_percent": 1.0}},
        "overrides": {"Product-A": {"yield_drop": {"threshold_pct": 5.0}}},
    }
    resolved = resolve_config("Product-A", cfg)
    assert resolved["yield_drop"]["threshold_pct"] == 5.0
    assert resolved["yield_drop"]["min_lots"] == 3
    assert resolved["bin_surge"]["multiplier"] == 2.0
