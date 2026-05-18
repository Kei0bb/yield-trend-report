import logging
from functools import lru_cache

from app.utils.csv_loader import PRODUCT_CONFIG_CSV, read_csv_robust

logger = logging.getLogger(__name__)

# Sentinel used in bin_mapping resolution for "any process"
ANY_PROCESS = "*"
DEFAULT_BIN_GROUP = "default"


@lru_cache(maxsize=None)
def load_product_config() -> dict[str, dict[str, str]] | None:
    """Load product_config.csv and return {nickname: {display_name, cp_product_id, ft_product_id, bin_group}}.

    Returns None when the file does not exist (falls back to DB enumeration or mock).
    Result is cached for the lifetime of the process; restart server after editing the CSV.
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
        config[nickname] = {
            "display_name": row.get("display_name", "").strip() or nickname,
            "cp_product_id": row.get("cp_product_id", "").strip(),
            "ft_product_id": row.get("ft_product_id", "").strip(),
            "bin_group": row.get("bin_group", "").strip() or DEFAULT_BIN_GROUP,
            "ft_processes": row.get("ft_processes", "").strip(),
            "slt_processes": row.get("slt_processes", "").strip(),
        }

    if not config:
        return None

    logger.info("Loaded product_config.csv: %d nicknames", len(config))
    return config


def resolve_product_ids(nickname: str, process: str) -> list[str]:
    """Resolve a nickname + process to a list of DB PRODUCT_IDs.

    Supports ';'-delimited multi-ID values and '%' wildcards for LIKE queries.
    Returns [nickname] as-is when product_config.csv is absent.
    """
    config = load_product_config()
    if config is None or nickname not in config:
        return [nickname] if nickname else []

    key = f"{process.lower()}_product_id"
    raw = config[nickname].get(key, "")
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

    Returns None when no sub-process filter is configured (use exact process match).
    Example: ft_processes="FT1;FT2" → ["FT1", "FT2"] when process="FT"
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


def resolve_bin_group(nickname: str) -> str:
    """Return the bin_group identifier for a nickname."""
    config = load_product_config()
    if config is None or nickname not in config:
        return DEFAULT_BIN_GROUP
    return config[nickname].get("bin_group", DEFAULT_BIN_GROUP)


def group_by_display_name(nicknames: list[str]) -> dict[str, list[str]]:
    """Group nicknames by their resolved display_name (insertion-order preserved)."""
    groups: dict[str, list[str]] = {}
    for nickname in nicknames:
        display = resolve_display_name(nickname)
        groups.setdefault(display, []).append(nickname)
    return groups
