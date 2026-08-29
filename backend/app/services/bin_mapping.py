import logging
from functools import lru_cache

import pandas as pd

from app.services.product_config import ANY_PROCESS, DEFAULT_BIN_GROUP
from app.utils.csv_loader import BIN_MAPPINGS_DIR, LEGACY_BIN_GROUP_CSV, read_csv_robust

logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def load_bin_mapping(bin_group: str) -> dict[str, dict[int, str]]:
    """Load bin_mappings/<bin_group>.csv and return {process: {bin_code: group_name}}.

    Supports two CSV formats:
    - With 'process' column: per-process mapping  (process, bin_code, bin_group_name)
    - Without 'process' column: all-process mapping  (bin_code, bin_group_name)

    Falls back to legacy bin_group.csv when bin_group == 'default'.
    Returns {} when the file does not exist.
    Result is cached; restart server after editing mapping files.
    """
    if not bin_group:
        return {}

    csv_path = BIN_MAPPINGS_DIR / f"{bin_group}.csv"
    if not csv_path.exists():
        if bin_group == DEFAULT_BIN_GROUP:
            return _load_legacy_bin_mapping()
        logger.warning(
            "Bin mapping file not found: %s  "
            "(Check the bin_group value in product_config.yaml matches the filename)",
            csv_path,
        )
        return {}

    df = read_csv_robust(csv_path)
    if df.empty:
        logger.warning("Bin mapping file is empty: %s", csv_path)
        return {}

    name_col = (
        "bin_group_name" if "bin_group_name" in df.columns
        else "bin_group" if "bin_group" in df.columns
        else None
    )
    if "bin_code" not in df.columns or name_col is None:
        logger.warning(
            "Bin mapping %s: missing required columns (bin_code + bin_group_name). "
            "Detected: %s",
            csv_path, list(df.columns),
        )
        return {}

    result: dict[str, dict[int, str]] = {}
    has_process_col = "process" in df.columns
    skipped = 0
    for _, row in df.iterrows():
        code_str = row.get("bin_code", "").strip()
        name = row.get(name_col, "").strip()
        if not code_str or not name:
            skipped += 1
            continue
        try:
            code_int = int(code_str)
        except ValueError:
            logger.warning("Bin mapping %s: non-numeric bin_code %r — skipped", csv_path, code_str)
            skipped += 1
            continue
        proc = (row.get("process", "").strip().upper() if has_process_col else "") or ANY_PROCESS
        result.setdefault(proc, {})[code_int] = name

    logger.info(
        "Loaded bin mapping %s: %d entries (%d skipped)",
        csv_path.name, sum(len(m) for m in result.values()), skipped,
    )
    return result


def _load_legacy_bin_mapping() -> dict[str, dict[int, str]]:
    """Load the legacy backend/bin_group.csv as {ANY_PROCESS: {code: name}}."""
    if not LEGACY_BIN_GROUP_CSV.exists():
        return {}
    df = read_csv_robust(LEGACY_BIN_GROUP_CSV)
    if df.empty or "bin_code" not in df.columns:
        return {}
    name_col = "bin_group_name" if "bin_group_name" in df.columns else "bin_group"
    if name_col not in df.columns:
        return {}
    mapping: dict[int, str] = {}
    for _, row in df.iterrows():
        code = row["bin_code"].strip()
        name = row[name_col].strip()
        if code and name:
            try:
                mapping[int(code)] = name
            except ValueError:
                pass
    return {ANY_PROCESS: mapping} if mapping else {}


def apply_bin_groups(df: pd.DataFrame, bin_group: str, process: str) -> pd.DataFrame:
    """Map numeric raw_bin_code values to group names via the bin mapping CSV.

    Lookup priority:
    1. Exact process match in the mapping file
    2. Wildcard '*' row (no process column or blank process)
    Falls back to the DB's BIN_NAME column when no mapping is found.

    Rows with a NULL/non-numeric raw_bin_code are tolerated: the SLT query outer-
    joins its bin table, so a lot with zero fail bins arrives as a header row with
    no bin at all. Such rows keep a null bin_code (the aggregator then counts them
    for yield and gross die only) instead of raising on the int conversion.
    """
    df = df.copy()
    proc_mappings = load_bin_mapping(bin_group)
    proc_key = (process or ANY_PROCESS).upper()

    mapping: dict[int, str] = {}
    for key in (proc_key, ANY_PROCESS):
        if key in proc_mappings:
            for code, name in proc_mappings[key].items():
                mapping.setdefault(code, name)

    if mapping:
        codes = pd.to_numeric(df["raw_bin_code"], errors="coerce").astype("Int64")
        df["bin_code"] = codes.map(mapping).fillna(df["bin_name"])
    else:
        df["bin_code"] = df["bin_name"]
    return df
