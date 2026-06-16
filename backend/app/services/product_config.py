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


def _parse_process_entry(entry):
    """Return (major: str|None, subs: list[str]).

    None major means the major row is suppressed (subs-only config).

    Accepted forms:
      scalar  ft: cFT1            → major='cFT1', subs=[]
      list    cp: [CP, CP1, CP2]  → major='CP' (first), subs=['CP1','CP2']
      list-1  ft: [cFT1]          → major='cFT1', subs=[]
      dict    cp: {major: CP, subs: [CP1, CP2]}
      subs-only cp: {subs: [CP1, CP2]} → major=None, subs=['CP1','CP2']
      major-only cp: {major: CP}       → major='CP', subs=[]
    """
    if entry is None:
        return None, []
    if isinstance(entry, dict):
        major_raw = entry.get("major")
        major = str(major_raw).strip() if major_raw not in (None, "") else None
        subs_raw = entry.get("subs") or []
        if isinstance(subs_raw, str):
            subs_raw = [subs_raw]
        subs = [str(s).strip() for s in subs_raw if str(s).strip()]
        return major, subs
    if isinstance(entry, (list, tuple)):
        vals = [str(v).strip() for v in entry if str(v).strip()]
        if not vals:
            return None, []
        return vals[0], vals[1:]
    # scalar
    s = str(entry).strip()
    return (s or None), []


def _config_from_yaml() -> dict[str, dict[str, str]] | None:
    """Parse product_config.yaml into the flat internal shape.

    Schema (per product, all fields except product_id optional):
        products:
          <nickname>:
            display_name: ...
            product_id: ...            # single id; '%' LIKE wildcard allowed
            bin_group: ...
            bin_groups: {ft: ..., slt: ...}   # optional per-process overrides
            processes:                 # DB PROCESS values per logical process
              cp: CP                  # scalar → single major row
              ft: [cFT1, cFT2]        # list → first=major, rest=sub rows
              slt: {major: cSLT1}     # dict with optional 'subs' key
              # subs-only: cp: {subs: [CP1, CP2]} → no major row, sub rows only

    Per process (cp/ft/slt), three internal keys are stored:
      <p>_set   : "1" when the key was present in the YAML processes mapping
      <p>_major : the DB PROCESS value for the major row, or "" when suppressed
      <p>_subs  : ";"-joined sub-process DB PROCESS values

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

        row: dict[str, str] = {
            "display_name": str(entry.get("display_name") or name).strip() or name,
            "product_id": str(entry.get("product_id") or "").strip(),
            "bin_group": str(entry.get("bin_group") or "").strip() or DEFAULT_BIN_GROUP,
            "ft_bin_group": str(bin_groups.get("ft") or "").strip(),
            "slt_bin_group": str(bin_groups.get("slt") or "").strip(),
        }

        for proc in ("cp", "ft", "slt"):
            if isinstance(processes, dict) and proc in processes:
                major, subs = _parse_process_entry(processes[proc])
                row[f"{proc}_set"] = "1"
                row[f"{proc}_major"] = major or ""
                row[f"{proc}_subs"] = ";".join(subs)
            else:
                row[f"{proc}_set"] = ""
                row[f"{proc}_major"] = ""
                row[f"{proc}_subs"] = ""

        config[name] = row
    return config or None


@lru_cache(maxsize=None)
def load_product_config() -> dict[str, dict[str, str]] | None:
    """Load product configuration as {nickname: {display_name, product_id, bin_group, ...}}.

    FT/SLT data lives in the CP schema under the *same* PRODUCT_ID as CP,
    distinguished only by the PROCESS column (e.g. 'cFT1'), so a product has a
    single `product_id`; per-process PROCESS values come from cp/ft/slt_major
    and cp/ft/slt_subs.

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


def resolve_major_process(nickname: str, process: str) -> str | None:
    """The DB PROCESS value the major row queries, or None to suppress the major row.

    Unconfigured process key → the literal process name (preserves default behavior).
    """
    config = load_product_config()
    if config is None or nickname not in config:
        return process.upper()
    entry = config[nickname]
    if entry.get(f"{process.lower()}_set") != "1":
        return process.upper()          # key absent → default literal
    major = entry.get(f"{process.lower()}_major", "")
    return major or None                # present but empty → suppress major row


def resolve_sub_processes(nickname: str, process: str) -> list[str]:
    """Sub-process DB PROCESS values shown as indented sub rows ([] when none)."""
    config = load_product_config()
    if config is None or nickname not in config:
        return []
    raw = config[nickname].get(f"{process.lower()}_subs", "")
    return [v for v in (x.strip() for x in raw.split(";")) if v]


def resolve_process_filter(nickname: str, process: str) -> list[str] | None:
    """DB PROCESS values for the merged/major view (Report + Explore-no-sub + dashboard).

    Returns [major] when a major is set, else the subs list, else None
    (caller then queries using the literal process name).

    Used by yield_service.py (Report/PDF) and lot_service.py (Explore fallback).
    """
    config = load_product_config()
    if config is None or nickname not in config:
        return None
    if config[nickname].get(f"{process.lower()}_set") != "1":
        return None
    major = config[nickname].get(f"{process.lower()}_major", "")
    if major:
        return [major]
    subs = resolve_sub_processes(nickname, process)
    return subs or None


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
