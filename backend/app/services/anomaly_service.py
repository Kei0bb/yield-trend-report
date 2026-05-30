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


def evaluate(lots: list, config: dict) -> list[dict]:
    """Compare the latest lot against the prior lots and return warning dicts.

    `lots` is ordered oldest→newest. Each lot exposes `.yield_pct` and
    `.bin_breakdown` (items with `.bin_name`, `.percent`, `.bin_codes`).
    `config` is a resolved threshold dict (see resolve_config).
    Returns [] when there is no latest+past pair to compare.
    """
    if len(lots) < 2:
        return []

    latest, past = lots[-1], lots[:-1]
    warnings: list[dict] = []

    # --- B: yield drop vs past average ---
    yd = config.get("yield_drop", {})
    min_lots = yd.get("min_lots", 3)
    threshold = yd.get("threshold_pct", 3.0)
    if len(past) >= min_lots:
        past_avg = sum(l.yield_pct for l in past) / len(past)
        drop = past_avg - latest.yield_pct
        if drop >= threshold:
            warnings.append({
                "type": "yield_drop",
                "message": f"前期比 -{drop:.1f}% (閾値 -{threshold:.1f}%)",
                "severity": "warn",
            })

    # --- C: fail-bin surge vs past average per bin ---
    bs = config.get("bin_surge", {})
    multiplier = bs.get("multiplier", 2.0)
    min_percent = bs.get("min_percent", 1.0)
    past_pct: dict[str, list[float]] = {}
    bin_codes_by_name: dict[str, list[int]] = {}
    for lot in past:
        for b in lot.bin_breakdown:
            past_pct.setdefault(b.bin_name, []).append(b.percent)
            bin_codes_by_name.setdefault(b.bin_name, b.bin_codes)
    for b in latest.bin_breakdown:
        history = past_pct.get(b.bin_name)
        if not history:
            continue
        avg = sum(history) / len(history)
        if avg >= min_percent and b.percent >= avg * multiplier:
            codes = b.bin_codes or bin_codes_by_name.get(b.bin_name, [])
            warnings.append({
                "type": "bin_surge",
                "message": f"{b.bin_name} が過去平均の {b.percent / avg:.1f}倍",
                "severity": "warn",
                "bin_code": codes[0] if codes else None,
            })

    return warnings
