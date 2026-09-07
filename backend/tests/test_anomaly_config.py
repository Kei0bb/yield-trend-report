from app.services.anomaly_service import load_anomaly_config, resolve_config


def test_load_returns_defaults_and_overrides():
    cfg = load_anomaly_config()
    assert cfg["defaults"]["bin_surge"]["delta_pct"] == 5.0
    assert "Product-A" in cfg["overrides"]


def test_defaults_carry_no_yield_drop():
    # Yield alerts were removed; a stale yield_drop key would be dead config.
    assert "yield_drop" not in load_anomaly_config()["defaults"]


def test_resolve_without_override_returns_defaults():
    cfg = {"defaults": {"bin_surge": {"delta_pct": 3.0}}, "overrides": {}}
    resolved = resolve_config("Unknown", cfg)
    assert resolved["bin_surge"]["delta_pct"] == 3.0


def test_resolve_deep_merges_override():
    cfg = {
        "defaults": {"bin_surge": {"delta_pct": 3.0, "min_lots": 3}},
        "overrides": {"Product-A": {"bin_surge": {"delta_pct": 5.0}}},
    }
    resolved = resolve_config("Product-A", cfg)
    assert resolved["bin_surge"]["delta_pct"] == 5.0
    assert resolved["bin_surge"]["min_lots"] == 3
