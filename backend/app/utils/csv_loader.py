from pathlib import Path

import pandas as pd

# Paths relative to backend/ root
BACKEND_ROOT = Path(__file__).parent.parent.parent
BIN_MAPPINGS_DIR = BACKEND_ROOT / "bin_mappings"
PRODUCT_CONFIG_YAML = BACKEND_ROOT / "product_config.yaml"
LEGACY_BIN_GROUP_CSV = BACKEND_ROOT / "bin_group.csv"


def read_csv_robust(path: Path) -> pd.DataFrame:
    """Read a CSV file tolerantly.

    Handles: BOM (utf-8-sig), leading/trailing whitespace in column names,
    comment lines starting with '#', and NaN → empty string.
    """
    df = pd.read_csv(path, dtype=str, comment="#", encoding="utf-8-sig").fillna("")
    df.columns = [c.strip() for c in df.columns]
    return df
