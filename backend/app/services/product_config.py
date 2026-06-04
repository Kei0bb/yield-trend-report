import logging
from functools import lru_cache

import yaml

from app.utils.csv_loader import PRODUCT_CONFIG_YAML

logger = logging.getLogger(__name__)

# Sentinel used in bin_mapping resolution for "any process"
ANY_PROCESS = "*"
DEFAULT_BIN_GROUP = "default"


# Processes that share FT's bin-group fallback chain (slt → ft → bin_group).
_FT_FAMILY = {"SLT"}


def _as_str(val) -> str:
    """Normalise a scalar / list config value to a ';'-delimited string so the
    downstream resolvers (which split on ';'/',') work for both YAML lists and
    plain strings. Returns '' for None/empty."""
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        return ";".join(str(v).strip() for v in val if str(v).strip())
    return str(val).strip()


def _config_from_yaml() -> dict[str, dict[str, str]] | None:
    """Parse product_config.yaml into the flat internal shape.

    Schema (per product, all fields except product_id optional):
        products:
          <nickname>:
            display_name: ...
            product_id: ...            # single id; '%' LIKE wildcard allowed
            bin_group: ...
            bin_groups: {ft: ..., slt: ...}   # optional per-process overrides
            processes: {cp: ..., ft: cFT1, slt: cSLT1}  # DB PROCESS values
    A bare top-level mapping (no `products:` key) is also accepted.
    """
    with PRODUCT_CONFIG_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    products = data.get("products", data) if isinstance(data, dict) else {}

    config: dict[str, dict[str, str]] = {}
    for nickname, entry in (products or {}).items():
        if not isinstance(entry, dict):
            continue
        name = str(nickname).strip()
        processes = entry.get("processes") or {}
        bin_groups = entry.get("bin_groups") or {}
        config[name] = {
            "display_name": _as_str(entry.get("display_name")) or name,
            "product_id": _as_str(entry.get("product_id")),
            "bin_group": _as_str(entry.get("bin_group")) or DEFAULT_BIN_GROUP,
            "ft_bin_group": _as_str(bin_groups.get("ft")),
            "slt_bin_group": _as_str(bin_groups.get("slt")),
            "cp_processes": _as_str(processes.get("cp")),
            "ft_processes": _as_str(processes.get("ft")),
            "slt_processes": _as_str(processes.get("slt")),
        }
    return config or None


@lru_cache(maxsize=None)
def load_product_config() -> dict[str, dict[str, str]] | None:
    """Load product configuration as {nickname: {display_name, product_id, bin_group, ...}}.

    FT/SLT data lives in the CP schema under the *same* PRODUCT_ID as CP,
    distinguished only by the PROCESS column (e.g. 'cFT1'), so a product has a
    single `product_id`; per-process PROCESS values come from cp/ft/slt_processes.

    Returns None when product_config.yaml is absent (falls back to DB enumeration
    or mock). Cached for the process lifetime — restart the server after edits.
    """
    if not PRODUCT_CONFIG_YAML.exists():
        return None
    config = _config_from_yaml()
    if config:
        logger.info("Loaded product_config.yaml: %d products", len(config))
    return config


def resolve_product_ids(nickname: str, process: str = "") -> list[str]:
    """Resolve a nickname to its DB PRODUCT_ID(s).

    Process-independent: every process shares the same product_id (CP schema),
    so `process` is accepted only for call-site compatibility. Supports
    ';'-delimited lists and '%' wildcards. Returns [nickname] as-is when
    product_config.yaml is absent.
    """
    config = load_product_config()
    if config is None or nickname not in config:
        return [nickname] if nickname else []

    raw = config[nickname].get("product_id", "")
    if not raw:
        return []
    ids = [pid.strip() for pid in raw.replace(",", ";").split(";")]
    return [pid for pid in ids if pid]


def resolve_display_name(nickname: str) -> str:
    """Return the display_name for a nickname, or the nickname itself if not configured."""
    config = load_product_config()
    if config is None or nickname not in config:
        return nickname
    return config[nickname].get("display_name", nickname)


def resolve_process_filter(nickname: str, process: str) -> list[str] | None:
    """Return the list of DB PROCESS values to filter for a given nickname + process.

    Returns None when no filter is configured (use exact process match).
    Example: ft_processes="cFT1;cFT2" → ["cFT1", "cFT2"] when process="FT"
    """
    config = load_product_config()
    if config is None or nickname not in config:
        return None
    key = f"{process.lower()}_processes"
    raw = config[nickname].get(key, "")
    if not raw:
        return None
    values = [v.strip() for v in raw.replace(",", ";").split(";")]
    return [v for v in values if v] or None


def resolve_bin_group(nickname: str, process: str = "") -> str:
    """Return the bin_group identifier for a nickname, optionally process-specific.

    Lookup order:
    1. <process>_bin_group  (e.g. ft_bin_group, slt_bin_group) — if set
    2. bin_group            — shared fallback
    SLT falls back to ft_bin_group before bin_group.
    """
    config = load_product_config()
    if config is None or nickname not in config:
        return DEFAULT_BIN_GROUP
    entry = config[nickname]
    if process:
        proc_key = f"{process.lower()}_bin_group"
        specific = entry.get(proc_key, "")
        if not specific and process.upper() in _FT_FAMILY:
            specific = entry.get("ft_bin_group", "")
        if specific:
            return specific
    return entry.get("bin_group", "") or DEFAULT_BIN_GROUP


def group_by_display_name(nicknames: list[str]) -> dict[str, list[str]]:
    """Group nicknames by their resolved display_name (insertion-order preserved)."""
    groups: dict[str, list[str]] = {}
    for nickname in nicknames:
        display = resolve_display_name(nickname)
        groups.setdefault(display, []).append(nickname)
    return groups


def primary_product_id(nickname: str) -> str:
    """The product's public product_id (process-independent). Falls back to the
    nickname itself when unconfigured."""
    config = load_product_config()
    if config is None or nickname not in config:
        return nickname
    return config[nickname].get("product_id", "") or nickname


def _reverse_product_id_map() -> dict[str, str]:
    """Map every configured product_id back to its nickname."""
    config = load_product_config()
    rev: dict[str, str] = {}
    if not config:
        return rev
    for nickname, entry in config.items():
        pid = entry.get("product_id", "")
        if pid:
            rev.setdefault(pid, nickname)
    return rev


def nickname_for_product_id(product_id: str) -> str | None:
    """Reverse-resolve a product_id to its nickname, or None if not found."""
    return _reverse_product_id_map().get(product_id)


def to_nicknames(product_ids: list[str]) -> list[str]:
    """Map UI-facing product_ids to internal nicknames.

    Falls back to the value as-is when it is not a known product_id (so plain
    nicknames and mock/unconfigured ids still resolve). Order preserved.
    """
    return [nickname_for_product_id(pid) or pid for pid in product_ids]


def list_products() -> list[dict[str, str]]:
    """Public product list for the UI: one entry per configured nickname,
    exposing the product_id + display_name (no nickname leaked)."""
    config = load_product_config()
    if not config:
        return []
    return [
        {"product_id": primary_product_id(nick), "display_name": entry.get("display_name", nick)}
        for nick, entry in config.items()
    ]
