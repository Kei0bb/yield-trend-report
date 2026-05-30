import copy
import logging
from functools import lru_cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

ANOMALY_CONFIG_YAML = Path(__file__).parent.parent.parent / "anomaly_config.yaml"

_EMPTY_CONFIG: dict = {
    "defaults": {
        "yield_drop": {"threshold_pct": 3.0, "min_lots": 3},
        "bin_surge": {"multiplier": 2.0, "min_percent": 1.0},
    },
    "overrides": {},
}


@lru_cache(maxsize=1)
def load_anomaly_config() -> dict:
    """Load anomaly_config.yaml. Falls back to built-in defaults when absent.

    Cached for the process lifetime; restart the server after editing the YAML.
    """
    if not ANOMALY_CONFIG_YAML.exists():
        logger.warning("anomaly_config.yaml not found at %s — using built-in defaults",
                       ANOMALY_CONFIG_YAML)
        return copy.deepcopy(_EMPTY_CONFIG)
    with ANOMALY_CONFIG_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("defaults", copy.deepcopy(_EMPTY_CONFIG["defaults"]))
    data.setdefault("overrides", {})
    return data


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def resolve_config(nickname: str, config: dict) -> dict:
    """Return the effective threshold config for a product: defaults deep-merged
    with overrides[nickname]."""
    defaults = config.get("defaults", {})
    override = config.get("overrides", {}).get(nickname, {})
    return _deep_merge(defaults, override)
