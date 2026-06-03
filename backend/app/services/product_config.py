import logging
from functools import lru_cache

from app.utils.csv_loader import PRODUCT_CONFIG_CSV, read_csv_robust

logger = logging.getLogger(__name__)

# Sentinel used in bin_mapping resolution for "any process"
ANY_PROCESS = "*"
DEFAULT_BIN_GROUP = "default"


# Processes that share FT's bin-group fallback chain (slt → ft → bin_group).
_FT_FAMILY = {"SLT"}


@lru_cache(maxsize=None)
def load_product_config() -> dict[str, dict[str, str]] | None:
    """Load product_config.csv and return {nickname: {display_name, product_id, bin_group, ...}}.

    FT/SLT data now lives in the CP schema under the *same* PRODUCT_ID as CP,
    distinguished only by the PROCESS column (e.g. 'cFT1'). So a product has a
    single `product_id`; the per-process PROCESS values come from
    cp_processes / ft_processes / slt_processes.

    `product_id` falls back to the legacy `cp_product_id` column for backward
    compatibility. Returns None when the file does not exist (falls back to DB
    enumeration or mock). Cached for the process lifetime — restart after edits.
    """
    if not PRODUCT_CONFIG_CSV.exists():
        return None

    df = read_csv_robust(PRODUCT_CONFIG_CSV)
    if "nickname" not in df.columns:
        logger.warning(
            "product_config.csv: 'nickname' column not found. "
            "Check the header row and file encoding (must be UTF-8). "
            "Detected columns: %s",
            list(df.columns),
        )
        return None

    config: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        nickname = row["nickname"].strip()
        if not nickname or nickname.startswith("#"):
            continue
        product_id = (row.get("product_id", "").strip()
                      or row.get("cp_product_id", "").strip())
        config[nickname] = {
            "display_name": row.get("display_name", "").strip() or nickname,
            "product_id": product_id,
            "bin_group": row.get("bin_group", "").strip() or DEFAULT_BIN_GROUP,
            "ft_bin_group": row.get("ft_bin_group", "").strip(),
            "slt_bin_group": row.get("slt_bin_group", "").strip(),
            "cp_processes": row.get("cp_processes", "").strip(),
            "ft_processes": row.get("ft_processes", "").strip(),
            "slt_processes": row.get("slt_processes", "").strip(),
        }

    if not config:
        return None

    logger.info("Loaded product_config.csv: %d nicknames", len(config))
    return config


def resolve_product_ids(nickname: str, process: str = "") -> list[str]:
    """Resolve a nickname to its DB PRODUCT_ID(s).

    Process-independent: every process shares the same product_id (CP schema),
    so `process` is accepted only for call-site compatibility. Supports
    ';'-delimited lists and '%' wildcards. Returns [nickname] as-is when
    product_config.csv is absent.
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
